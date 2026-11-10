// Generado automáticamente con `python -m cdd.export_schema`. No editar a mano.
// Formato compatible con supabase-js: createClient<Database>(url, publishableKey)
export type Json = string | number | boolean | null | { [key: string]: Json | undefined } | Json[];

export type Database = {
  public: {
    Tables: {
      agent_definitions: {
        Row: {
          code: string;
          number: number;
          family: string;
          name_es: string;
          version: string;
          status: string;
          enabled: boolean;
          execution_model: string;
          allowed_tools: string[];
          input_contract: string;
          output_contract: string;
          rules: string[];
          unit_cost_usd: number;
          max_cost_per_run_usd: number;
          fallback: string;
          updated_at: string;
        };
        Insert: {
          code: string;
          number: number;
          family: string;
          name_es: string;
          version: string;
          status: string;
          enabled?: boolean;
          execution_model: string;
          allowed_tools?: string[];
          input_contract: string;
          output_contract: string;
          rules?: string[];
          unit_cost_usd?: number;
          max_cost_per_run_usd?: number;
          fallback?: string;
          updated_at?: string;
        };
        Update: {
          code?: string;
          number?: number;
          family?: string;
          name_es?: string;
          version?: string;
          status?: string;
          enabled?: boolean;
          execution_model?: string;
          allowed_tools?: string[];
          input_contract?: string;
          output_contract?: string;
          rules?: string[];
          unit_cost_usd?: number;
          max_cost_per_run_usd?: number;
          fallback?: string;
          updated_at?: string;
        };
        Relationships: [
        ];
      };
      bibliographic_references: {
        Row: {
          id: string;
          slug: string;
          ref_type: string;
          authors: string[];
          title: string;
          container_title: string | null;
          publisher: string | null;
          year: number | null;
          edition: string | null;
          language: string | null;
          identifiers: Json;
          identifier_check: string;
          checked_at: string | null;
          created_at: string;
          tier: string;
          doi: string | null;
          url: string | null;
          openalex_id: string | null;
          venue_type: string | null;
          cited_by_count: number | null;
          is_retracted: boolean;
          retraction_checked_at: string | null;
          source_connector: string | null;
        };
        Insert: {
          id?: string;
          slug: string;
          ref_type: string;
          authors?: string[];
          title: string;
          container_title?: string | null;
          publisher?: string | null;
          year?: number | null;
          edition?: string | null;
          language?: string | null;
          identifiers?: Json;
          identifier_check?: string;
          checked_at?: string | null;
          created_at?: string;
          tier?: string;
          doi?: string | null;
          url?: string | null;
          openalex_id?: string | null;
          venue_type?: string | null;
          cited_by_count?: number | null;
          is_retracted?: boolean;
          retraction_checked_at?: string | null;
          source_connector?: string | null;
        };
        Update: {
          id?: string;
          slug?: string;
          ref_type?: string;
          authors?: string[];
          title?: string;
          container_title?: string | null;
          publisher?: string | null;
          year?: number | null;
          edition?: string | null;
          language?: string | null;
          identifiers?: Json;
          identifier_check?: string;
          checked_at?: string | null;
          created_at?: string;
          tier?: string;
          doi?: string | null;
          url?: string | null;
          openalex_id?: string | null;
          venue_type?: string | null;
          cited_by_count?: number | null;
          is_retracted?: boolean;
          retraction_checked_at?: string | null;
          source_connector?: string | null;
        };
        Relationships: [
        ];
      };
      budget_policies: {
        Row: {
          id: string;
          scope: string;
          scope_ref: string;
          period: string;
          limit_usd: number;
          auto_approve_below_usd: number;
          active: boolean;
          created_at: string;
        };
        Insert: {
          id?: string;
          scope: string;
          scope_ref?: string;
          period: string;
          limit_usd: number;
          auto_approve_below_usd?: number;
          active?: boolean;
          created_at?: string;
        };
        Update: {
          id?: string;
          scope?: string;
          scope_ref?: string;
          period?: string;
          limit_usd?: number;
          auto_approve_below_usd?: number;
          active?: boolean;
          created_at?: string;
        };
        Relationships: [
        ];
      };
      claim_reviews: {
        Row: {
          id: string;
          claim_id: string;
          reviewer_id: string | null;
          action: string;
          previous: Json;
          changes: Json;
          note: string;
          created_at: string;
        };
        Insert: {
          id?: string;
          claim_id: string;
          reviewer_id?: string | null;
          action: string;
          previous?: Json;
          changes?: Json;
          note?: string;
          created_at?: string;
        };
        Update: {
          id?: string;
          claim_id?: string;
          reviewer_id?: string | null;
          action?: string;
          previous?: Json;
          changes?: Json;
          note?: string;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "claim_reviews_reviewer_id_fkey"; columns: ["reviewer_id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
          { foreignKeyName: "claim_reviews_claim_id_fkey"; columns: ["claim_id"]; isOneToOne: false; referencedRelation: "claims"; referencedColumns: ["id"] },
        ];
      };
      claims: {
        Row: {
          id: string;
          slug: string;
          topic_id: string | null;
          statement: string;
          asserted_by: string;
          discipline: string;
          category: Database["public"]["Enums"]["epistemic_category"];
          is_event: boolean;
          date_start: number | null;
          date_end: number | null;
          date_precision: Database["public"]["Enums"]["date_precision"];
          date_label: string;
          place_entity_id: string | null;
          subject_entity_id: string | null;
          consensus_note: string;
          insufficient_evidence_note: string;
          future_research_note: string;
          review_status: Database["public"]["Enums"]["review_status"];
          visibility: Database["public"]["Enums"]["visibility"];
          content_sha256: string;
          created_by: string | null;
          created_at: string;
          updated_at: string;
          origin: string;
          generated_by: Json;
          run_id: string | null;
        };
        Insert: {
          id?: string;
          slug: string;
          topic_id?: string | null;
          statement: string;
          asserted_by?: string;
          discipline: string;
          category: Database["public"]["Enums"]["epistemic_category"];
          is_event?: boolean;
          date_start?: number | null;
          date_end?: number | null;
          date_precision?: Database["public"]["Enums"]["date_precision"];
          date_label?: string;
          place_entity_id?: string | null;
          subject_entity_id?: string | null;
          consensus_note?: string;
          insufficient_evidence_note?: string;
          future_research_note?: string;
          review_status?: Database["public"]["Enums"]["review_status"];
          visibility?: Database["public"]["Enums"]["visibility"];
          content_sha256: string;
          created_by?: string | null;
          created_at?: string;
          updated_at?: string;
          origin?: string;
          generated_by?: Json;
          run_id?: string | null;
        };
        Update: {
          id?: string;
          slug?: string;
          topic_id?: string | null;
          statement?: string;
          asserted_by?: string;
          discipline?: string;
          category?: Database["public"]["Enums"]["epistemic_category"];
          is_event?: boolean;
          date_start?: number | null;
          date_end?: number | null;
          date_precision?: Database["public"]["Enums"]["date_precision"];
          date_label?: string;
          place_entity_id?: string | null;
          subject_entity_id?: string | null;
          consensus_note?: string;
          insufficient_evidence_note?: string;
          future_research_note?: string;
          review_status?: Database["public"]["Enums"]["review_status"];
          visibility?: Database["public"]["Enums"]["visibility"];
          content_sha256?: string;
          created_by?: string | null;
          created_at?: string;
          updated_at?: string;
          origin?: string;
          generated_by?: Json;
          run_id?: string | null;
        };
        Relationships: [
          { foreignKeyName: "claims_created_by_fkey"; columns: ["created_by"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
          { foreignKeyName: "claims_place_entity_id_fkey"; columns: ["place_entity_id"]; isOneToOne: false; referencedRelation: "entities"; referencedColumns: ["id"] },
          { foreignKeyName: "claims_subject_entity_id_fkey"; columns: ["subject_entity_id"]; isOneToOne: false; referencedRelation: "entities"; referencedColumns: ["id"] },
          { foreignKeyName: "claims_run_id_fkey"; columns: ["run_id"]; isOneToOne: false; referencedRelation: "harness_runs"; referencedColumns: ["id"] },
          { foreignKeyName: "claims_topic_id_fkey"; columns: ["topic_id"]; isOneToOne: false; referencedRelation: "topics"; referencedColumns: ["id"] },
        ];
      };
      cost_ledger: {
        Row: {
          id: number;
          run_id: string | null;
          user_id: string | null;
          agent_code: string | null;
          provider: string;
          model: string;
          kind: string;
          input_tokens: number;
          output_tokens: number;
          amount_usd: number;
          cache_hit: boolean;
          note: string;
          created_at: string;
        };
        Insert: {
          id?: number;
          run_id?: string | null;
          user_id?: string | null;
          agent_code?: string | null;
          provider?: string;
          model?: string;
          kind: string;
          input_tokens?: number;
          output_tokens?: number;
          amount_usd?: number;
          cache_hit?: boolean;
          note?: string;
          created_at?: string;
        };
        Update: {
          id?: number;
          run_id?: string | null;
          user_id?: string | null;
          agent_code?: string | null;
          provider?: string;
          model?: string;
          kind?: string;
          input_tokens?: number;
          output_tokens?: number;
          amount_usd?: number;
          cache_hit?: boolean;
          note?: string;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "cost_ledger_user_id_fkey"; columns: ["user_id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
          { foreignKeyName: "cost_ledger_run_id_fkey"; columns: ["run_id"]; isOneToOne: false; referencedRelation: "harness_runs"; referencedColumns: ["id"] },
        ];
      };
      document_chunks: {
        Row: {
          id: string;
          document_id: string;
          ordinal: number;
          locator: string;
          content: string;
          content_tsv: unknown | null;
          embedding: string | null;
          embedding_model: string;
          injection_risk: boolean;
          injection_signals: string[];
          created_at: string;
        };
        Insert: {
          id?: string;
          document_id: string;
          ordinal: number;
          locator?: string;
          content: string;
          content_tsv?: unknown | null;
          embedding?: string | null;
          embedding_model?: string;
          injection_risk?: boolean;
          injection_signals?: string[];
          created_at?: string;
        };
        Update: {
          id?: string;
          document_id?: string;
          ordinal?: number;
          locator?: string;
          content?: string;
          content_tsv?: unknown | null;
          embedding?: string | null;
          embedding_model?: string;
          injection_risk?: boolean;
          injection_signals?: string[];
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "document_chunks_document_id_fkey"; columns: ["document_id"]; isOneToOne: false; referencedRelation: "documents"; referencedColumns: ["id"] },
        ];
      };
      documents: {
        Row: {
          id: string;
          slug: string | null;
          title: string;
          doc_kind: string;
          authors: string[];
          institution: string | null;
          published_date: string | null;
          language: string;
          edition: string | null;
          identifier: string | null;
          license_code: string;
          rights_statement: string;
          provenance: Json;
          consulted_at: string | null;
          content_sha256: string;
          body: string;
          owner_id: string | null;
          visibility: Database["public"]["Enums"]["visibility"];
          review_status: Database["public"]["Enums"]["review_status"];
          cites: string[];
          created_at: string;
          updated_at: string;
          source_tier: string;
          doi: string | null;
        };
        Insert: {
          id?: string;
          slug?: string | null;
          title: string;
          doc_kind: string;
          authors?: string[];
          institution?: string | null;
          published_date?: string | null;
          language?: string;
          edition?: string | null;
          identifier?: string | null;
          license_code: string;
          rights_statement?: string;
          provenance?: Json;
          consulted_at?: string | null;
          content_sha256: string;
          body: string;
          owner_id?: string | null;
          visibility?: Database["public"]["Enums"]["visibility"];
          review_status?: Database["public"]["Enums"]["review_status"];
          cites?: string[];
          created_at?: string;
          updated_at?: string;
          source_tier?: string;
          doi?: string | null;
        };
        Update: {
          id?: string;
          slug?: string | null;
          title?: string;
          doc_kind?: string;
          authors?: string[];
          institution?: string | null;
          published_date?: string | null;
          language?: string;
          edition?: string | null;
          identifier?: string | null;
          license_code?: string;
          rights_statement?: string;
          provenance?: Json;
          consulted_at?: string | null;
          content_sha256?: string;
          body?: string;
          owner_id?: string | null;
          visibility?: Database["public"]["Enums"]["visibility"];
          review_status?: Database["public"]["Enums"]["review_status"];
          cites?: string[];
          created_at?: string;
          updated_at?: string;
          source_tier?: string;
          doi?: string | null;
        };
        Relationships: [
          { foreignKeyName: "documents_license_code_fkey"; columns: ["license_code"]; isOneToOne: false; referencedRelation: "licenses"; referencedColumns: ["code"] },
          { foreignKeyName: "documents_owner_id_fkey"; columns: ["owner_id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
        ];
      };
      entities: {
        Row: {
          id: string;
          slug: string;
          kind: Database["public"]["Enums"]["entity_kind"];
          name: string;
          description: string;
          attributes: Json;
          topic_id: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          slug: string;
          kind: Database["public"]["Enums"]["entity_kind"];
          name: string;
          description?: string;
          attributes?: Json;
          topic_id?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          slug?: string;
          kind?: Database["public"]["Enums"]["entity_kind"];
          name?: string;
          description?: string;
          attributes?: Json;
          topic_id?: string | null;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "entities_topic_id_fkey"; columns: ["topic_id"]; isOneToOne: false; referencedRelation: "topics"; referencedColumns: ["id"] },
        ];
      };
      entity_relations: {
        Row: {
          id: string;
          subject_id: string;
          predicate: string;
          object_id: string;
          evidence_claim_id: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          subject_id: string;
          predicate: string;
          object_id: string;
          evidence_claim_id?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          subject_id?: string;
          predicate?: string;
          object_id?: string;
          evidence_claim_id?: string | null;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "entity_relations_subject_id_fkey"; columns: ["subject_id"]; isOneToOne: false; referencedRelation: "entities"; referencedColumns: ["id"] },
          { foreignKeyName: "entity_relations_claim_fk"; columns: ["evidence_claim_id"]; isOneToOne: false; referencedRelation: "claims"; referencedColumns: ["id"] },
          { foreignKeyName: "entity_relations_object_id_fkey"; columns: ["object_id"]; isOneToOne: false; referencedRelation: "entities"; referencedColumns: ["id"] },
        ];
      };
      evidence_links: {
        Row: {
          id: string;
          claim_id: string;
          chunk_id: string;
          reference_id: string | null;
          stance: Database["public"]["Enums"]["evidence_stance"];
          exact_fragment: string;
          locator: string;
          note: string;
          verification_status: string;
          verified_at: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          claim_id: string;
          chunk_id: string;
          reference_id?: string | null;
          stance: Database["public"]["Enums"]["evidence_stance"];
          exact_fragment: string;
          locator?: string;
          note?: string;
          verification_status?: string;
          verified_at?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          claim_id?: string;
          chunk_id?: string;
          reference_id?: string | null;
          stance?: Database["public"]["Enums"]["evidence_stance"];
          exact_fragment?: string;
          locator?: string;
          note?: string;
          verification_status?: string;
          verified_at?: string | null;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "evidence_links_claim_id_fkey"; columns: ["claim_id"]; isOneToOne: false; referencedRelation: "claims"; referencedColumns: ["id"] },
          { foreignKeyName: "evidence_links_chunk_id_fkey"; columns: ["chunk_id"]; isOneToOne: false; referencedRelation: "document_chunks"; referencedColumns: ["id"] },
          { foreignKeyName: "evidence_links_reference_id_fkey"; columns: ["reference_id"]; isOneToOne: false; referencedRelation: "bibliographic_references"; referencedColumns: ["id"] },
        ];
      };
      experiences: {
        Row: {
          id: string;
          run_id: string | null;
          owner_id: string;
          modality: string;
          title: string;
          knowledge_packet: Json;
          knowledge_packet_sha256: string;
          experience_spec: Json;
          status: string;
          published_by: string | null;
          published_at: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          run_id?: string | null;
          owner_id: string;
          modality: string;
          title: string;
          knowledge_packet: Json;
          knowledge_packet_sha256: string;
          experience_spec: Json;
          status?: string;
          published_by?: string | null;
          published_at?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          run_id?: string | null;
          owner_id?: string;
          modality?: string;
          title?: string;
          knowledge_packet?: Json;
          knowledge_packet_sha256?: string;
          experience_spec?: Json;
          status?: string;
          published_by?: string | null;
          published_at?: string | null;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "experiences_run_id_fkey"; columns: ["run_id"]; isOneToOne: false; referencedRelation: "harness_runs"; referencedColumns: ["id"] },
          { foreignKeyName: "experiences_owner_id_fkey"; columns: ["owner_id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
          { foreignKeyName: "experiences_published_by_fkey"; columns: ["published_by"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
        ];
      };
      harness_checkpoints: {
        Row: {
          id: string;
          run_id: string;
          task_key: string;
          state: Database["public"]["Enums"]["run_state"];
          output_sha256: string;
          snapshot: Json;
          created_at: string;
        };
        Insert: {
          id?: string;
          run_id: string;
          task_key: string;
          state: Database["public"]["Enums"]["run_state"];
          output_sha256: string;
          snapshot: Json;
          created_at?: string;
        };
        Update: {
          id?: string;
          run_id?: string;
          task_key?: string;
          state?: Database["public"]["Enums"]["run_state"];
          output_sha256?: string;
          snapshot?: Json;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "harness_checkpoints_run_id_fkey"; columns: ["run_id"]; isOneToOne: false; referencedRelation: "harness_runs"; referencedColumns: ["id"] },
        ];
      };
      harness_events: {
        Row: {
          id: number;
          run_id: string;
          task_key: string | null;
          level: string;
          event_type: string;
          message: string;
          data: Json;
          created_at: string;
        };
        Insert: {
          id?: number;
          run_id: string;
          task_key?: string | null;
          level?: string;
          event_type: string;
          message: string;
          data?: Json;
          created_at?: string;
        };
        Update: {
          id?: number;
          run_id?: string;
          task_key?: string | null;
          level?: string;
          event_type?: string;
          message?: string;
          data?: Json;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "harness_events_run_id_fkey"; columns: ["run_id"]; isOneToOne: false; referencedRelation: "harness_runs"; referencedColumns: ["id"] },
        ];
      };
      harness_runs: {
        Row: {
          id: string;
          investigation_id: string;
          owner_id: string;
          state: Database["public"]["Enums"]["run_state"];
          previous_state: Database["public"]["Enums"]["run_state"] | null;
          budget_usd: number;
          spent_usd: number;
          estimated_usd: number;
          requires_approval: boolean;
          approved_by: string | null;
          approved_at: string | null;
          pause_requested: boolean;
          cancel_requested: boolean;
          queued: boolean;
          worker_lease_until: string | null;
          plan: Json;
          result: Json;
          error: string | null;
          contract_version: string;
          created_at: string;
          updated_at: string;
          finished_at: string | null;
        };
        Insert: {
          id?: string;
          investigation_id: string;
          owner_id: string;
          state?: Database["public"]["Enums"]["run_state"];
          previous_state?: Database["public"]["Enums"]["run_state"] | null;
          budget_usd?: number;
          spent_usd?: number;
          estimated_usd?: number;
          requires_approval?: boolean;
          approved_by?: string | null;
          approved_at?: string | null;
          pause_requested?: boolean;
          cancel_requested?: boolean;
          queued?: boolean;
          worker_lease_until?: string | null;
          plan?: Json;
          result?: Json;
          error?: string | null;
          contract_version?: string;
          created_at?: string;
          updated_at?: string;
          finished_at?: string | null;
        };
        Update: {
          id?: string;
          investigation_id?: string;
          owner_id?: string;
          state?: Database["public"]["Enums"]["run_state"];
          previous_state?: Database["public"]["Enums"]["run_state"] | null;
          budget_usd?: number;
          spent_usd?: number;
          estimated_usd?: number;
          requires_approval?: boolean;
          approved_by?: string | null;
          approved_at?: string | null;
          pause_requested?: boolean;
          cancel_requested?: boolean;
          queued?: boolean;
          worker_lease_until?: string | null;
          plan?: Json;
          result?: Json;
          error?: string | null;
          contract_version?: string;
          created_at?: string;
          updated_at?: string;
          finished_at?: string | null;
        };
        Relationships: [
          { foreignKeyName: "harness_runs_approved_by_fkey"; columns: ["approved_by"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
          { foreignKeyName: "harness_runs_investigation_id_fkey"; columns: ["investigation_id"]; isOneToOne: false; referencedRelation: "investigations"; referencedColumns: ["id"] },
          { foreignKeyName: "harness_runs_owner_id_fkey"; columns: ["owner_id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
        ];
      };
      harness_tasks: {
        Row: {
          id: string;
          run_id: string;
          task_key: string;
          agent_code: string;
          phase: Database["public"]["Enums"]["run_state"];
          depends_on: string[];
          status: Database["public"]["Enums"]["task_status"];
          attempts: number;
          max_attempts: number;
          budget_usd: number;
          cost_usd: number;
          allowed_tools: string[];
          agent_version: string;
          input: Json;
          output: Json;
          completion_criteria: string;
          error: string | null;
          started_at: string | null;
          finished_at: string | null;
          created_at: string;
        };
        Insert: {
          id?: string;
          run_id: string;
          task_key: string;
          agent_code: string;
          phase: Database["public"]["Enums"]["run_state"];
          depends_on?: string[];
          status?: Database["public"]["Enums"]["task_status"];
          attempts?: number;
          max_attempts?: number;
          budget_usd?: number;
          cost_usd?: number;
          allowed_tools?: string[];
          agent_version?: string;
          input?: Json;
          output?: Json;
          completion_criteria?: string;
          error?: string | null;
          started_at?: string | null;
          finished_at?: string | null;
          created_at?: string;
        };
        Update: {
          id?: string;
          run_id?: string;
          task_key?: string;
          agent_code?: string;
          phase?: Database["public"]["Enums"]["run_state"];
          depends_on?: string[];
          status?: Database["public"]["Enums"]["task_status"];
          attempts?: number;
          max_attempts?: number;
          budget_usd?: number;
          cost_usd?: number;
          allowed_tools?: string[];
          agent_version?: string;
          input?: Json;
          output?: Json;
          completion_criteria?: string;
          error?: string | null;
          started_at?: string | null;
          finished_at?: string | null;
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "harness_tasks_agent_code_fkey"; columns: ["agent_code"]; isOneToOne: false; referencedRelation: "agent_definitions"; referencedColumns: ["code"] },
          { foreignKeyName: "harness_tasks_run_id_fkey"; columns: ["run_id"]; isOneToOne: false; referencedRelation: "harness_runs"; referencedColumns: ["id"] },
        ];
      };
      investigations: {
        Row: {
          id: string;
          owner_id: string;
          prompt: string;
          prompt_sha256: string;
          preferences: Json;
          intent: Json;
          status: string;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id?: string;
          owner_id: string;
          prompt: string;
          prompt_sha256: string;
          preferences?: Json;
          intent?: Json;
          status?: string;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          owner_id?: string;
          prompt?: string;
          prompt_sha256?: string;
          preferences?: Json;
          intent?: Json;
          status?: string;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          { foreignKeyName: "investigations_owner_id_fkey"; columns: ["owner_id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
        ];
      };
      learning_progress: {
        Row: {
          id: string;
          user_id: string;
          experience_id: string;
          completed_missions: string[];
          answers: Json;
          score: number;
          unlocked_stage: number;
          updated_at: string;
        };
        Insert: {
          id?: string;
          user_id: string;
          experience_id: string;
          completed_missions?: string[];
          answers?: Json;
          score?: number;
          unlocked_stage?: number;
          updated_at?: string;
        };
        Update: {
          id?: string;
          user_id?: string;
          experience_id?: string;
          completed_missions?: string[];
          answers?: Json;
          score?: number;
          unlocked_stage?: number;
          updated_at?: string;
        };
        Relationships: [
          { foreignKeyName: "learning_progress_user_id_fkey"; columns: ["user_id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
          { foreignKeyName: "learning_progress_experience_id_fkey"; columns: ["experience_id"]; isOneToOne: false; referencedRelation: "experiences"; referencedColumns: ["id"] },
        ];
      };
      licenses: {
        Row: {
          code: string;
          name: string;
          url: string | null;
          allows_display: boolean;
          allows_excerpt: boolean;
          allows_full_text: boolean;
          allows_derivatives: boolean;
          requires_attribution: boolean;
          notes: string;
        };
        Insert: {
          code: string;
          name: string;
          url?: string | null;
          allows_display?: boolean;
          allows_excerpt?: boolean;
          allows_full_text?: boolean;
          allows_derivatives?: boolean;
          requires_attribution?: boolean;
          notes?: string;
        };
        Update: {
          code?: string;
          name?: string;
          url?: string | null;
          allows_display?: boolean;
          allows_excerpt?: boolean;
          allows_full_text?: boolean;
          allows_derivatives?: boolean;
          requires_attribution?: boolean;
          notes?: string;
        };
        Relationships: [
        ];
      };
      perspectives: {
        Row: {
          id: string;
          claim_id: string;
          label: string;
          tradition: string;
          summary: string;
          held_by: string;
          evidence_link_ids: string[];
          created_at: string;
        };
        Insert: {
          id?: string;
          claim_id: string;
          label: string;
          tradition: string;
          summary: string;
          held_by?: string;
          evidence_link_ids?: string[];
          created_at?: string;
        };
        Update: {
          id?: string;
          claim_id?: string;
          label?: string;
          tradition?: string;
          summary?: string;
          held_by?: string;
          evidence_link_ids?: string[];
          created_at?: string;
        };
        Relationships: [
          { foreignKeyName: "perspectives_claim_id_fkey"; columns: ["claim_id"]; isOneToOne: false; referencedRelation: "claims"; referencedColumns: ["id"] },
        ];
      };
      profiles: {
        Row: {
          id: string;
          display_name: string;
          preferred_language: string;
          academic_level: string;
          created_at: string;
          updated_at: string;
        };
        Insert: {
          id: string;
          display_name?: string;
          preferred_language?: string;
          academic_level?: string;
          created_at?: string;
          updated_at?: string;
        };
        Update: {
          id?: string;
          display_name?: string;
          preferred_language?: string;
          academic_level?: string;
          created_at?: string;
          updated_at?: string;
        };
        Relationships: [
          { foreignKeyName: "profiles_id_fkey"; columns: ["id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
        ];
      };
      topics: {
        Row: {
          id: string;
          slug: string;
          title: string;
          summary: string;
          sort_order: number;
          content_status: string;
          open_questions: string[];
          created_at: string;
        };
        Insert: {
          id?: string;
          slug: string;
          title: string;
          summary?: string;
          sort_order?: number;
          content_status?: string;
          open_questions?: string[];
          created_at?: string;
        };
        Update: {
          id?: string;
          slug?: string;
          title?: string;
          summary?: string;
          sort_order?: number;
          content_status?: string;
          open_questions?: string[];
          created_at?: string;
        };
        Relationships: [
        ];
      };
      user_roles: {
        Row: {
          user_id: string;
          role: Database["public"]["Enums"]["app_role"];
          granted_by: string | null;
          granted_at: string;
        };
        Insert: {
          user_id: string;
          role?: Database["public"]["Enums"]["app_role"];
          granted_by?: string | null;
          granted_at?: string;
        };
        Update: {
          user_id?: string;
          role?: Database["public"]["Enums"]["app_role"];
          granted_by?: string | null;
          granted_at?: string;
        };
        Relationships: [
          { foreignKeyName: "user_roles_granted_by_fkey"; columns: ["granted_by"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
          { foreignKeyName: "user_roles_user_id_fkey"; columns: ["user_id"]; isOneToOne: false; referencedRelation: "users"; referencedColumns: ["id"] },
        ];
      };
    };
    Views: { [_ in never]: never };
    Functions: {
      current_app_role: { Args: {  }; Returns: Database["public"]["Enums"]["app_role"] };
      hybrid_search: { Args: { query_text?: string | null; query_embedding?: string | null; match_count?: number | null; mode?: string | null; embedding_model?: string | null }; Returns: { chunk_id: string; document_id: string; document_title: string; locator: string; content: string; text_rank: number; semantic_score: number; score: number; injection_risk: boolean }[] };
      is_owner: { Args: {  }; Returns: boolean };
      is_staff: { Args: {  }; Returns: boolean };
    };
    Enums: {
      app_role: "owner" | "editor" | "user";
      date_precision: "exact_day" | "exact_year" | "approximate_year" | "range" | "decade" | "century" | "disputed" | "unknown";
      entity_kind: "person" | "place" | "manuscript" | "edition" | "event" | "concept" | "tradition" | "institution" | "theory" | "hypothesis" | "artifact" | "period";
      epistemic_category: "empirical_fact" | "historical_document" | "scholarly_consensus" | "scientific_hypothesis" | "philosophical_argument" | "theological_interpretation" | "religious_belief" | "contested" | "uncorroborated" | "open_question";
      evidence_stance: "supports" | "challenges" | "contextualizes" | "qualifies";
      review_status: "draft" | "pending_review" | "reviewed" | "rejected";
      run_state: "CREATED" | "AUTHORIZED" | "PLANNED" | "ACQUIRING" | "ANALYZING" | "CROSS_EXAMINING" | "VERIFYING" | "PACKAGING" | "RENDERING" | "QA" | "READY" | "PUBLISHED" | "FAILED" | "CANCELLED" | "PAUSED" | "AWAITING_APPROVAL" | "LICENSE_BLOCKED" | "PARTIAL" | "BUDGET_EXHAUSTED";
      task_status: "pending" | "queued" | "running" | "succeeded" | "failed" | "skipped" | "cancelled" | "blocked";
      visibility: "public" | "private";
    };
    CompositeTypes: { [_ in never]: never };
  };
};

export type Tables<T extends keyof Database["public"]["Tables"]> = Database["public"]["Tables"][T]["Row"];
export type TablesInsert<T extends keyof Database["public"]["Tables"]> = Database["public"]["Tables"][T]["Insert"];
export type TablesUpdate<T extends keyof Database["public"]["Tables"]> = Database["public"]["Tables"][T]["Update"];
export type Enums<T extends keyof Database["public"]["Enums"]> = Database["public"]["Enums"][T];
