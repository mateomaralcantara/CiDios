"""Genera la referencia de la API de las tablas a partir de la base real (catálogo de Postgres).

Produce:
  docs/API-TABLAS.md                          columnas, claves, permisos RLS y ejemplos REST por tabla
  packages/contracts/database.types.ts        tipos TypeScript (formato compatible con supabase-js)

Uso: python -m cdd.export_schema [--url postgresql://...]
"""
from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(os.environ.get("CDD_REPO_ROOT", Path(__file__).resolve().parents[3]))

CMD_ES = {"SELECT": "leer", "INSERT": "crear", "UPDATE": "modificar", "DELETE": "borrar", "ALL": "leer y escribir"}
ROLE_ES = {"anon": "visitante", "authenticated": "usuario autenticado", "public": "todos"}

TS_SCALARS = {
    "uuid": "string", "text": "string", "character varying": "string", "citext": "string",
    "integer": "number", "bigint": "number", "smallint": "number", "numeric": "number", "real": "number",
    "double precision": "number", "boolean": "boolean", "jsonb": "Json", "json": "Json",
    "timestamp with time zone": "string", "timestamp without time zone": "string", "date": "string",
    "tsvector": "unknown", "vector": "string",
}


def _ts_type(fmt: str, enums: set[str]) -> str:
    base = re.sub(r"\(.*\)", "", fmt).replace("public.", "").strip()
    is_array = base.endswith("[]")
    base = base.removesuffix("[]")
    t = f'Database["public"]["Enums"]["{base}"]' if base in enums else TS_SCALARS.get(base, "unknown")
    return f"{t}[]" if is_array else t


def introspect(conn: psycopg.Connection) -> dict:
    q = lambda sql, *a: conn.execute(sql, a).fetchall()  # noqa: E731
    tables = q("""select c.relname as name, obj_description(c.oid) as comment, c.relrowsecurity as rls,
                         c.relforcerowsecurity as force_rls
                  from pg_class c join pg_namespace n on n.oid = c.relnamespace
                  where n.nspname = 'public' and c.relkind = 'r' order by c.relname""")
    cols = q("""select c.relname as tbl, a.attname as col, format_type(a.atttypid, a.atttypmod) as type,
                       not a.attnotnull as nullable, pg_get_expr(d.adbin, d.adrelid) as default,
                       a.attidentity <> '' or a.attgenerated <> '' as generated
                from pg_attribute a join pg_class c on c.oid = a.attrelid
                join pg_namespace n on n.oid = c.relnamespace
                left join pg_attrdef d on d.adrelid = a.attrelid and d.adnum = a.attnum
                where n.nspname = 'public' and c.relkind = 'r' and a.attnum > 0 and not a.attisdropped
                order by c.relname, a.attnum""")
    cons = q("""select c.relname as tbl, con.contype as type, pg_get_constraintdef(con.oid) as def,
                       con.conname as name, fr.relname as ref_table
                from pg_constraint con join pg_class c on c.oid = con.conrelid
                join pg_namespace n on n.oid = c.relnamespace left join pg_class fr on fr.oid = con.confrelid
                where n.nspname = 'public' and con.contype in ('p','f','u') order by c.relname, con.contype""")
    policies = q("""select tablename as tbl, policyname as name, roles::text[] as roles, cmd, qual, with_check
                    from pg_policies where schemaname = 'public' order by tablename, policyname""")
    grants = q("""select table_name as tbl, grantee, string_agg(privilege_type, ',' order by privilege_type) as privs
                  from information_schema.role_table_grants
                  where table_schema = 'public' and grantee in ('anon','authenticated')
                  group by 1, 2 order by 1, 2""")
    col_grants = q("""select table_name as tbl, grantee, privilege_type as priv, string_agg(column_name, ', ') as cols
                      from information_schema.column_privileges
                      where table_schema = 'public' and grantee = 'authenticated' and privilege_type = 'UPDATE'
                      group by 1, 2, 3""")
    enums = q("""select t.typname as name, array_agg(e.enumlabel order by e.enumsortorder) as values
                 from pg_type t join pg_enum e on e.enumtypid = t.oid join pg_namespace n on n.oid = t.typnamespace
                 where n.nspname = 'public' group by t.typname order by t.typname""")
    funcs = q("""select p.proname as name, pg_get_function_arguments(p.oid) as args, pg_get_function_result(p.oid) as result,
                        obj_description(p.oid) as comment, p.proargnames as argnames, p.proargmodes::text[] as argmodes,
                        array(select format_type(t, null) from unnest(coalesce(p.proallargtypes, p.proargtypes::oid[])) t) as argtypes
                 from pg_proc p join pg_namespace n on n.oid = p.pronamespace
                 where n.nspname = 'public' and has_function_privilege('authenticated', p.oid, 'execute')
                   and p.proname in ('hybrid_search','current_app_role','is_owner','is_staff')
                 order by p.proname""")
    return {"tables": tables, "cols": cols, "cons": cons, "policies": policies, "grants": grants,
            "col_grants": col_grants, "enums": enums, "funcs": funcs}


def _by(rows: list[dict], key: str = "tbl") -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for r in rows:
        out.setdefault(r[key], []).append(r)
    return out


def _who(cond: str | None) -> str:
    c = (cond or "true").strip()
    if c == "is_owner()":
        return "solo propietario"
    if c == "is_staff()":
        return "solo editor o propietario"
    if c == "true":
        return "todas las filas"
    if "auth.uid()" in c and "is_staff()" not in c and "is_owner()" not in c and "visibility" not in c and "status" not in c:
        return "solo las propias"
    return "según condición"


def effective_access(policies: list[dict], grants: dict[str, str], role: str, column_update: bool = False) -> str:
    granted = set((grants.get(role) or "").split(","))
    if column_update and role == "authenticated":
        granted.add("UPDATE")
    parts: dict[str, set[str]] = {}
    for p in policies:
        if role not in p["roles"] and "public" not in p["roles"]:
            continue
        cmds = ["SELECT", "INSERT", "UPDATE", "DELETE"] if p["cmd"] == "ALL" else [p["cmd"]]
        for c in cmds:
            if c not in granted:
                continue
            who = _who(p["qual"] if c in ("SELECT", "DELETE") or p["qual"] else p["with_check"])
            if c == "INSERT":
                who = _who(p["with_check"] or p["qual"])
            parts.setdefault(c, set()).add(who)
    if not parts:
        return "—"

    def merge(ws: set[str]) -> str:  # las políticas permisivas se combinan con OR
        if "todas las filas" in ws:
            return "todas las filas"
        if ws == {"solo las propias", "solo editor o propietario"}:
            return "las propias; editor/propietario: todas"
        if ws == {"solo las propias", "solo propietario"}:
            return "las propias; propietario: todas"
        return ws.pop() if len(ws) == 1 else "según condición"

    order = ["SELECT", "INSERT", "UPDATE", "DELETE"]
    return "; ".join(f"{CMD_ES[c]} ({merge(parts[c])})" for c in order if c in parts)


def render_markdown(s: dict) -> str:
    cols, cons, pols, grants = _by(s["cols"]), _by(s["cons"]), _by(s["policies"]), _by(s["grants"])
    colg = {r["tbl"]: r["cols"] for r in s["col_grants"]}
    L = ["# API de las tablas de Supabase", "",
         "> Generado automáticamente desde el catálogo de la base con `python -m cdd.export_schema`. No editar a mano.", "",
         "Cada tabla del esquema `public` queda expuesta por la **API REST de Supabase** (PostgREST) en",
         "`https://<proyecto>.supabase.co/rest/v1/<tabla>` y por `supabase-js`. **RLS decide qué filas ve y modifica cada rol**:",
         "", "- **visitante** = petición con la clave pública (`anon` / *publishable key*) sin sesión iniciada;",
         "- **usuario autenticado** = petición con la clave pública + el token de sesión (`Authorization: Bearer <access_token>`);",
         "- el **rol de aplicación** (`owner`, `editor`, `user`) está en `user_roles` y lo evalúan las funciones `is_owner()` / `is_staff()`.",
         "", "La clave `service_role` / *secret key* **ignora RLS**: solo se usa en el backend y **nunca** en el navegador.",
         "", "Además de la API REST directa, la API propia del proyecto (FastAPI, `/v1/...`) ofrece operaciones de más alto nivel",
         "(investigaciones, HARNESS, misiones calificadas en el servidor, centro de control). Ver `docs/ARCHITECTURE.md`.", "",
         "## Resumen", "", "| Tabla | Descripción | Visitante | Usuario autenticado |", "|---|---|---|---|"]
    for t in s["tables"]:
        g = {r["grantee"]: r["privs"] for r in grants.get(t["name"], [])}
        tp = pols.get(t["name"], [])
        cu = t["name"] in colg
        L.append(f"| [`{t['name']}`](#{t['name']}) | {t['comment'] or ''} | {effective_access(tp, g, 'anon')} | "
                 f"{effective_access(tp, g, 'authenticated', cu)} |")
    L += ["", "Calculado a partir de los permisos de la tabla y de sus políticas RLS. «Según condición» = ver la política exacta en la sección de la tabla.", ""]
    for t in s["tables"]:
        n = t["name"]
        L += [f"## {n}", "", t["comment"] or "", "",
              f"RLS: **{'activado' if t['rls'] else 'DESACTIVADO'}**" + (" (forzado)" if t["force_rls"] else ""), "",
              "| Columna | Tipo | Nulo | Por defecto |", "|---|---|---|---|"]
        for c in cols.get(n, []):
            L.append(f"| `{c['col']}` | `{c['type']}` | {'sí' if c['nullable'] else 'no'} | {('`' + c['default'] + '`') if c['default'] else ''} |")
        keys = cons.get(n, [])
        if keys:
            L += ["", "**Claves y relaciones**", ""]
            for k in keys:
                kind = {"p": "Primaria", "f": "Foránea", "u": "Única"}[k["type"]]
                L.append(f"- {kind}: `{k['def']}`")
        L += ["", "**Políticas RLS**", ""]
        for p in pols.get(n, []):
            roles = ", ".join(ROLE_ES.get(r, r) for r in p["roles"])
            cond = p["qual"] or p["with_check"] or "true"
            extra = f"; al escribir: `{p['with_check']}`" if p["qual"] and p["with_check"] and p["with_check"] != p["qual"] else ""
            L.append(f"- `{p['name']}` — {roles} puede **{CMD_ES.get(p['cmd'], p['cmd'])}** si `{cond}`{extra}")
        if n in colg and "UPDATE" not in ({r["grantee"]: r["privs"] for r in grants.get(n, [])}.get("authenticated") or ""):
            L.append(f"- Columnas que un usuario puede modificar: {colg[n]}")
        g = {r["grantee"]: r["privs"] for r in grants.get(n, [])}
        if not g:
            L.append("- Sin acceso directo para visitantes ni usuarios: solo el backend la escribe y lee.")
        L += ["", "**Ejemplos**", "", "```bash",
              f'curl "$SUPABASE_URL/rest/v1/{n}?select=*&limit=10" \\',
              '  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"', "```", "",
              "```ts", f"const {{ data, error }} = await supabase.from('{n}').select('*').limit(10)", "```", ""]
    L += ["## Funciones (RPC)", ""]
    for f in s["funcs"]:
        L += [f"### {f['name']}", "", f["comment"] or "", "", f"- Argumentos: `{f['args'] or '—'}`", f"- Devuelve: `{f['result']}`", ""]
    L += ["```ts", "const { data } = await supabase.rpc('hybrid_search', {",
          "  query_text: 'Códice de Leningrado', query_embedding: null, match_count: 10, mode: 'text' })", "```", "",
          "La búsqueda semántica necesita el vector de la consulta (384 dimensiones), que calcula el backend: usa",
          "`GET /v1/library/search?q=...&mode=hybrid` de la API del proyecto para búsquedas híbridas.", "",
          "## Tipos enumerados", ""]
    for e in s["enums"]:
        L.append(f"- `{e['name']}`: " + ", ".join(f"`{v}`" for v in e["values"]))
    return "\n".join(L) + "\n"


def render_types(s: dict) -> str:
    enums = {e["name"] for e in s["enums"]}
    cols, cons = _by(s["cols"]), _by(s["cons"])
    L = ["// Generado automáticamente con `python -m cdd.export_schema`. No editar a mano.",
         "// Formato compatible con supabase-js: createClient<Database>(url, publishableKey)",
         "export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];", "",
         "export type Database = {", "  public: {", "    Tables: {"]
    for t in s["tables"]:
        n = t["name"]
        L.append(f"      {n}: {{")
        for mode in ("Row", "Insert", "Update"):
            L.append(f"        {mode}: {{")
            for c in cols.get(n, []):
                ts = _ts_type(c["type"], enums) + (" | null" if c["nullable"] else "")
                optional = mode == "Update" or (mode == "Insert" and (c["nullable"] or c["default"] or c["generated"]))
                L.append(f"          {c['col']}{'?' if optional else ''}: {ts};")
            L.append("        };")
        L.append("        Relationships: [")
        for k in cons.get(n, []):
            if k["type"] == "f":
                m = re.match(r"FOREIGN KEY \(([^)]*)\) REFERENCES [\w.]*?(\w+)\(([^)]*)\)", k["def"])
                if m:
                    L.append(f'          {{ foreignKeyName: "{k["name"]}"; columns: ["{m.group(1)}"]; isOneToOne: false; '
                             f'referencedRelation: "{m.group(2)}"; referencedColumns: ["{m.group(3)}"] }},')
        L += ["        ];", "      };"]
    L += ["    };", "    Views: { [_ in never]: never };", "    Functions: {"]
    for f in s["funcs"]:
        names, modes, types = f["argnames"] or [], f["argmodes"], f["argtypes"]
        ins, outs = [], []
        for i, nm in enumerate(names):
            mode = modes[i] if modes else "i"
            (outs if mode == "t" else ins).append((nm, _ts_type(types[i], enums)))
        args = "; ".join(f"{a}?: {t} | null" for a, t in ins) or ""
        if outs:
            ret = "{ " + "; ".join(f"{a}: {t}" for a, t in outs) + " }[]"
        else:
            ret = _ts_type(f["result"].replace("public.", ""), enums)
        L.append(f"      {f['name']}: {{ Args: {{ {args} }}; Returns: {ret} }};")
    L += ["    };", "    Enums: {"]
    for e in s["enums"]:
        L.append(f"      {e['name']}: " + " | ".join(f'"{v}"' for v in e["values"]) + ";")
    L += ["    };", "    CompositeTypes: { [_ in never]: never };", "  };", "};", "",
          'export type Tables<T extends keyof Database["public"]["Tables"]> = Database["public"]["Tables"][T]["Row"];',
          'export type TablesInsert<T extends keyof Database["public"]["Tables"]> = Database["public"]["Tables"][T]["Insert"];',
          'export type TablesUpdate<T extends keyof Database["public"]["Tables"]> = Database["public"]["Tables"][T]["Update"];',
          'export type Enums<T extends keyof Database["public"]["Enums"]> = Database["public"]["Enums"][T];', ""]
    return "\n".join(L)


def main(url: str) -> None:
    with psycopg.connect(url, row_factory=dict_row) as conn:
        s = introspect(conn)
    (ROOT / "docs" / "API-TABLAS.md").write_text(render_markdown(s), encoding="utf-8")
    (ROOT / "packages" / "contracts" / "database.types.ts").write_text(render_types(s), encoding="utf-8")
    print(f"→ docs/API-TABLAS.md y packages/contracts/database.types.ts ({len(s['tables'])} tablas, "
          f"{len(s['policies'])} políticas, {len(s['funcs'])} funciones)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url")
    a = ap.parse_args()
    url = a.url or os.environ.get("CDD_DATABASE_URL")
    if not url:
        from .config import get_settings
        url = get_settings().database_url
    main(url)
