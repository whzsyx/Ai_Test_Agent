import type {
  AgentDescriptor,
  ApiDocRecord,
  ApiDocUploadRequest,
  ConversationResponse,
  EmailConfigPublic,
  EmailConfigCreateRequest,
  EmailConfigActionResponse,
  EmailConfigConnectionTestResponse,
  EmailConfigUpdateRequest,
  ExecutionEvent,
  HealthResponse,
  ModeDescriptor,
  ModelConfigActionResponse,
  ModelConfigConnectionTestResponse,
  ModelConfigPublic,
  ModelConfigUpdateRequest,
  SessionDetail,
  InputAttachment,
  UploadedAttachmentRecord,
  SessionSummary,
  SessionSummaryPage,
  SessionReplayResponse,
  ToolArtifactRecord,
  ToolApprovalRequest,
  ToolDescriptor,
  ToolJobDetail,
  ToolJobRecord,
  KnowledgeGraphResponse,
  KnowledgeProjectDeleteResponse,
  KnowledgeProjectSummary,
  SkillDescriptor,
  SkillBulkInstallResponse,
  SkillInstallRequest,
  SkillMarketplaceInstallRequest,
  SkillMarketplaceSearchResponse,
  SkillUploadRequest,
  SkillUpsertRequest,
  SessionVerificationResponse,
} from "../types";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export const api = {
  getHealth(): Promise<HealthResponse> {
    return request("/api/v1/health");
  },
  listKnowledgeProjects(): Promise<KnowledgeProjectSummary[]> {
    return request("/api/v1/knowledge/projects");
  },
  getKnowledgeGraph(projectScope: string): Promise<KnowledgeGraphResponse> {
    const params = new URLSearchParams({ project_scope: projectScope });
    return request(`/api/v1/knowledge/graph?${params.toString()}`);
  },
  deleteKnowledgeProject(projectScope: string): Promise<KnowledgeProjectDeleteResponse> {
    const params = new URLSearchParams({ project_scope: projectScope });
    return request(`/api/v1/knowledge/project?${params.toString()}`, {
      method: "DELETE",
    });
  },
  listAgents(): Promise<AgentDescriptor[]> {
    return request("/api/v1/registry/agents");
  },
  listTools(): Promise<ToolDescriptor[]> {
    return request("/api/v1/registry/tools");
  },
  listModes(): Promise<ModeDescriptor[]> {
    return request("/api/v1/registry/modes");
  },
  listSkills(): Promise<SkillDescriptor[]> {
    return request("/api/v1/registry/skills");
  },
  getSkill(skillKey: string): Promise<SkillDescriptor> {
    return request(`/api/v1/registry/skills/${encodeURIComponent(skillKey)}`);
  },
  upsertSkill(skillKey: string, payload: SkillUpsertRequest): Promise<SkillDescriptor> {
    return request(`/api/v1/registry/skills/${encodeURIComponent(skillKey)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  installSkill(payload: SkillInstallRequest): Promise<SkillDescriptor> {
    return request("/api/v1/registry/skills/install", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  uploadSkill(payload: SkillUploadRequest): Promise<SkillDescriptor | SkillBulkInstallResponse> {
    return request("/api/v1/registry/skills/upload", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  searchSkillMarketplace(source: string, q: string, limit = 20): Promise<SkillMarketplaceSearchResponse> {
    const params = new URLSearchParams({ source, q, limit: String(limit) });
    return request(`/api/v1/registry/skills/marketplaces/search?${params.toString()}`);
  },
  installMarketplaceSkill(payload: SkillMarketplaceInstallRequest): Promise<SkillDescriptor | SkillBulkInstallResponse> {
    return request("/api/v1/registry/skills/marketplaces/install", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteSkill(skillKey: string): Promise<{ ok: boolean; message: string }> {
    return request(`/api/v1/registry/skills/${encodeURIComponent(skillKey)}`, {
      method: "DELETE",
    });
  },
  listModelConfigs(): Promise<ModelConfigPublic[]> {
    return request("/api/v1/settings/models");
  },
  updateModelConfig(payload: ModelConfigUpdateRequest): Promise<ModelConfigPublic> {
    return request("/api/v1/settings/models", {
      method: "PUT",
      body: JSON.stringify(payload),
    });
  },
  editModelConfig(modelName: string, payload: ModelConfigUpdateRequest): Promise<ModelConfigPublic> {
    return request(`/api/v1/settings/models/${encodeURIComponent(modelName)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  activateModelConfig(modelName: string): Promise<ModelConfigActionResponse> {
    return request(`/api/v1/settings/models/${encodeURIComponent(modelName)}/activate`, {
      method: "POST",
    });
  },
  testModelConfigConnection(modelName: string): Promise<ModelConfigConnectionTestResponse> {
    return request(`/api/v1/settings/models/${encodeURIComponent(modelName)}/test-connection`, {
      method: "POST",
    });
  },
  deleteModelConfig(modelName: string): Promise<ModelConfigActionResponse> {
    return request(`/api/v1/settings/models/${encodeURIComponent(modelName)}`, {
      method: "DELETE",
    });
  },
  listEmailConfigs(): Promise<EmailConfigPublic[]> {
    return request("/api/v1/settings/email");
  },
  createEmailConfig(payload: EmailConfigCreateRequest): Promise<EmailConfigPublic> {
    return request("/api/v1/settings/email", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  updateEmailConfig(configId: number, payload: EmailConfigUpdateRequest): Promise<EmailConfigPublic> {
    return request(`/api/v1/settings/email/${configId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  activateEmailConfig(configId: number): Promise<EmailConfigActionResponse> {
    return request(`/api/v1/settings/email/${configId}/activate`, {
      method: "POST",
    });
  },
  testEmailConfigConnection(configId: number): Promise<EmailConfigConnectionTestResponse> {
    return request(`/api/v1/settings/email/${configId}/test-connection`, {
      method: "POST",
    });
  },
  deleteEmailConfig(configId: number): Promise<EmailConfigActionResponse> {
    return request(`/api/v1/settings/email/${configId}`, {
      method: "DELETE",
    });
  },
  createSession(
    title = "Enterprise Intelligent QA Session",
    modeKey = "default",
  ): Promise<SessionDetail> {
    return request("/api/v1/sessions", {
      method: "POST",
      body: JSON.stringify({
        title,
        mode_key: modeKey,
      }),
    });
  },
  listSessions(): Promise<SessionSummary[]> {
    return request("/api/v1/sessions");
  },
  listSessionsPage(limit = 10, offset = 0, modeKey?: string): Promise<SessionSummaryPage> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    });
    if (modeKey) {
      params.set("mode_key", modeKey);
    }
    return request(`/api/v1/sessions?${params.toString()}`);
  },
  getSession(sessionId: string): Promise<SessionDetail> {
    return request(`/api/v1/sessions/${sessionId}`);
  },
  updateSession(
    sessionId: string,
    payload: {
      mode_key?: string | null;
      preferred_model?: string | null;
      selected_agent?: string | null;
      metadata?: Record<string, unknown> | null;
    },
  ): Promise<SessionDetail> {
    return request(`/api/v1/sessions/${sessionId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  listApprovals(sessionId: string): Promise<ToolApprovalRequest[]> {
    return request(`/api/v1/sessions/${sessionId}/approvals`);
  },
  resolveApproval(
    sessionId: string,
    approvalId: string,
    decision: "approved" | "denied",
    reason?: string,
  ): Promise<ToolApprovalRequest> {
    return request(`/api/v1/sessions/${sessionId}/approvals/${approvalId}`, {
      method: "POST",
      body: JSON.stringify({
        decision,
        reason: reason || null,
      }),
    });
  },
  sendMessage(
    sessionId: string,
    content: string,
    modeKey?: string,
    attachments: InputAttachment[] = [],
  ): Promise<ConversationResponse> {
    return request(`/api/v1/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({
        content,
        mode_key: modeKey || null,
        attachments,
      }),
    });
  },
  listApiDocs(): Promise<ApiDocRecord[]> {
    return request("/api/v1/registry/api-docs");
  },
  getApiDoc(docId: string): Promise<ApiDocRecord> {
    return request(`/api/v1/registry/api-docs/${encodeURIComponent(docId)}`);
  },
  uploadApiDoc(payload: ApiDocUploadRequest): Promise<ApiDocRecord> {
    return request("/api/v1/registry/api-docs/upload", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  uploadAttachment(payload: {
    filename: string;
    content_base64: string;
    source?: string;
  }): Promise<UploadedAttachmentRecord> {
    return request("/api/v1/registry/attachments/upload", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  deleteApiDoc(docId: string): Promise<{ ok: boolean; deleted_id: string }> {
    return request(`/api/v1/registry/api-docs/${encodeURIComponent(docId)}`, {
      method: "DELETE",
    });
  },
  interruptSession(sessionId: string, reason?: string): Promise<SessionDetail> {
    return request(`/api/v1/sessions/${sessionId}/interrupt`, {
      method: "POST",
      body: JSON.stringify({
        reason: reason || null,
        source: "web_console",
      }),
    });
  },
  resumeSession(sessionId: string, reason?: string): Promise<ConversationResponse> {
    return request(`/api/v1/sessions/${sessionId}/resume`, {
      method: "POST",
      body: JSON.stringify({
        reason: reason || null,
        source: "web_console",
      }),
    });
  },
  replaySession(sessionId: string): Promise<SessionReplayResponse> {
    return request(`/api/v1/sessions/${sessionId}/replay`);
  },
  listToolJobs(sessionId: string): Promise<ToolJobRecord[]> {
    return request(`/api/v1/sessions/${sessionId}/tool-jobs`);
  },
  getToolJobDetail(sessionId: string, jobId: string): Promise<ToolJobDetail> {
    return request(`/api/v1/sessions/${sessionId}/tool-jobs/${jobId}`);
  },
  listArtifacts(sessionId: string): Promise<ToolArtifactRecord[]> {
    return request(`/api/v1/sessions/${sessionId}/artifacts`);
  },
  listVerifications(sessionId: string): Promise<SessionVerificationResponse> {
    return request(`/api/v1/sessions/${sessionId}/verifications`);
  },
  connectEvents(sessionId: string, onEvent: (event: ExecutionEvent) => void): EventSource {
    const source = new EventSource(`/api/v1/sessions/${sessionId}/events`);
    source.onmessage = (message) => {
      const payload = JSON.parse(message.data) as ExecutionEvent;
      onEvent(payload);
    };
    return source;
  },
};
