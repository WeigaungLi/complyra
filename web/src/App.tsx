import { useMemo, useState } from "react";
import {
  askQuestion,
  assignUserTenant,
  createTenant,
  createUser,
  decideApproval,
  fetchApprovals,
  fetchAudit,
  getApprovalResult,
  getIngestJob,
  ingestFile,
  listTenants,
  listUsers,
  login,
  logout
} from "./api";
import type {
  ApprovalResponse,
  AuditRecord,
  IngestJobResponse,
  RetrievedChunk,
  Tenant,
  UserAccount
} from "./types";
import "./styles.css";

const formatTimestamp = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
};

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export default function App() {
  const [username, setUsername] = useState("demo");
  const [password, setPassword] = useState("demo123");
  const [tenantId, setTenantId] = useState("default");
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [status, setStatus] = useState<string>("");

  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [retrieved, setRetrieved] = useState<RetrievedChunk[]>([]);
  const [approvalId, setApprovalId] = useState<string | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [latestJob, setLatestJob] = useState<IngestJobResponse | null>(null);

  const [auditLogs, setAuditLogs] = useState<AuditRecord[]>([]);
  const [approvals, setApprovals] = useState<ApprovalResponse[]>([]);
  const [approvalNote, setApprovalNote] = useState("");

  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [tenantName, setTenantName] = useState("");

  const [users, setUsers] = useState<UserAccount[]>([]);
  const [newUserName, setNewUserName] = useState("");
  const [newUserPassword, setNewUserPassword] = useState("");
  const [newUserRole, setNewUserRole] = useState("user");
  const [newUserDefaultTenant, setNewUserDefaultTenant] = useState("");
  const [assignUserId, setAssignUserId] = useState("");
  const [assignTenantId, setAssignTenantId] = useState("");

  const isAuthenticated = useMemo(() => Boolean(token), [token]);
  const isAdmin = role === "admin";
  const canApprove = role === "admin" || role === "auditor";

  const handleLogin = async () => {
    try {
      setStatus("Signing in...");
      const result = await login(username, password);
      setToken(result.access_token);
      setRole(result.role);
      if (result.default_tenant_id) {
        setTenantId(result.default_tenant_id);
      }
      setStatus("Signed in successfully.");
    } catch (error) {
      console.error(error);
      setStatus("Login failed. Check credentials.");
    }
  };

  const handleLogout = async () => {
    try {
      await logout(token);
    } catch (error) {
      console.error(error);
    }
    setToken(null);
    setRole(null);
    setAnswer("");
    setRetrieved([]);
    setApprovalId(null);
    setStatus("Logged out.");
  };

  const pollIngestJob = async (jobId: string) => {
    for (let attempt = 0; attempt < 40; attempt += 1) {
      const job = await getIngestJob(jobId, token);
      setLatestJob(job);
      if (job.status === "completed") {
        setStatus(`Ingest completed with ${job.chunks_indexed} indexed chunks.`);
        return;
      }
      if (job.status === "failed") {
        setStatus(`Ingest failed: ${job.error_message || "Unknown error"}`);
        return;
      }
      await delay(1500);
    }
    setStatus("Ingest is still running. Use the API to check job status later.");
  };

  const handleIngest = async () => {
    if (!file || !isAuthenticated) return;
    try {
      setStatus("Submitting ingest job...");
      const result = await ingestFile(file, tenantId, token);
      setStatus(`Ingest job queued: ${result.job_id}`);
      await pollIngestJob(result.job_id);
    } catch (error) {
      console.error(error);
      setStatus("Failed to submit ingest job.");
    }
  };

  const handleAsk = async () => {
    if (!question || !isAuthenticated) return;
    try {
      setStatus("Running retrieval...");
      const result = await askQuestion(question, tenantId, token);
      setRetrieved(result.retrieved);
      setApprovalId(result.approval_id ?? null);

      if (result.status === "pending_approval" && result.approval_id) {
        setAnswer("Answer is pending approval.");
        setStatus("Approval required. Waiting for reviewer decision.");
      } else {
        setAnswer(result.answer);
        setStatus("Answer ready.");
      }
    } catch (error) {
      console.error(error);
      setStatus("Chat request failed.");
    }
  };

  const handleRefreshApprovalResult = async () => {
    if (!approvalId || !isAuthenticated) return;
    try {
      const result = await getApprovalResult(approvalId, tenantId, token);
      if (result.status === "approved" && result.final_answer) {
        setAnswer(result.final_answer);
        setStatus("Approval completed and final answer is available.");
      } else if (result.status === "rejected") {
        setAnswer("The request was rejected by a reviewer.");
        setStatus("Approval rejected.");
      } else {
        setStatus("Approval is still pending.");
      }
    } catch (error) {
      console.error(error);
      setStatus("Failed to fetch approval result.");
    }
  };

  const handleAudit = async () => {
    if (!isAuthenticated) return;
    try {
      setStatus("Loading audit logs...");
      const result = await fetchAudit(token, 100);
      setAuditLogs(result);
      setStatus("Audit logs loaded.");
    } catch (error) {
      console.error(error);
      setStatus("Failed to load audit logs.");
    }
  };

  const handleLoadApprovals = async () => {
    if (!isAuthenticated) return;
    try {
      setStatus("Loading approvals...");
      const result = await fetchApprovals("pending", tenantId, token);
      setApprovals(result);
      setStatus("Approvals loaded.");
    } catch (error) {
      console.error(error);
      setStatus("Failed to load approvals.");
    }
  };

  const handleDecision = async (approval: ApprovalResponse, approved: boolean) => {
    if (!isAuthenticated) return;
    try {
      setStatus("Submitting decision...");
      await decideApproval(approval.approval_id, approved, approvalNote, token);
      setStatus("Decision submitted.");
      await handleLoadApprovals();
    } catch (error) {
      console.error(error);
      setStatus("Decision failed.");
    }
  };

  const handleLoadTenants = async () => {
    if (!isAuthenticated) return;
    try {
      const result = await listTenants(token);
      setTenants(result);
    } catch (error) {
      console.error(error);
      setStatus("Failed to load tenants.");
    }
  };

  const handleCreateTenant = async () => {
    if (!isAuthenticated || !tenantName) return;
    try {
      await createTenant(tenantName, token);
      setTenantName("");
      await handleLoadTenants();
      setStatus("Tenant created.");
    } catch (error) {
      console.error(error);
      setStatus("Failed to create tenant.");
    }
  };

  const handleLoadUsers = async () => {
    if (!isAuthenticated) return;
    try {
      const result = await listUsers(token);
      setUsers(result);
    } catch (error) {
      console.error(error);
      setStatus("Failed to load users.");
    }
  };

  const handleCreateUser = async () => {
    if (!isAuthenticated || !newUserName || !newUserPassword) return;
    try {
      await createUser(
        newUserName,
        newUserPassword,
        newUserRole,
        newUserDefaultTenant || null,
        token
      );
      setNewUserName("");
      setNewUserPassword("");
      await handleLoadUsers();
      setStatus("User created.");
    } catch (error) {
      console.error(error);
      setStatus("Failed to create user.");
    }
  };

  const handleAssignTenant = async () => {
    if (!isAuthenticated || !assignUserId || !assignTenantId) return;
    try {
      await assignUserTenant(assignUserId, assignTenantId, token);
      setAssignUserId("");
      setAssignTenantId("");
      setStatus("Tenant assigned.");
      await handleLoadUsers();
    } catch (error) {
      console.error(error);
      setStatus("Tenant assignment failed.");
    }
  };

  return (
    <div className="app">
      <header className="hero">
        <div>
          <p className="eyebrow">Complyra</p>
          <h1>Secure knowledge with a governed human-approval workflow.</h1>
          <p className="subtitle">
            Multi-tenant retrieval, RBAC, asynchronous ingestion, auditable approvals, and
            production observability.
          </p>
        </div>
        <div className="hero-card">
          <div className="badge">Complyra Console</div>
          <p className="hero-card-title">System Status</p>
          <p className="hero-card-text">{status || "Ready. Sign in to start."}</p>
          <div className="chip-row">
            <span className="chip">RBAC</span>
            <span className="chip">Tenant Scope</span>
            <span className="chip">Qdrant</span>
            <span className="chip">Approvals</span>
            <span className="chip">Audit</span>
          </div>
        </div>
      </header>

      <main className="grid">
        <section className="card" style={{ animationDelay: "0.05s" }}>
          <h2>Access</h2>
          <div className="field">
            <label>Username</label>
            <input value={username} onChange={(event) => setUsername(event.target.value)} />
          </div>
          <div className="field">
            <label>Password</label>
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          <div className="field">
            <label>Tenant ID</label>
            <input value={tenantId} onChange={(event) => setTenantId(event.target.value)} />
          </div>
          <div className="actions">
            <button onClick={handleLogin} disabled={isAuthenticated}>
              Sign In
            </button>
            <button className="ghost" onClick={handleLogout} disabled={!isAuthenticated}>
              Sign Out
            </button>
          </div>
          <p className="muted">Current role: {role || "anonymous"}</p>
        </section>

        <section className="card" style={{ animationDelay: "0.15s" }}>
          <h2>Ingest</h2>
          <div className="field">
            <label>Document</label>
            <input type="file" onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
          </div>
          <button onClick={handleIngest} disabled={!isAuthenticated || !file || !isAdmin}>
            Submit Ingest Job
          </button>
          {!isAdmin && isAuthenticated && <p className="muted">Admin role required to ingest files.</p>}
          {latestJob && (
            <div className="muted" style={{ marginTop: "12px" }}>
              Job `{latestJob.job_id}` status: {latestJob.status}
            </div>
          )}
        </section>

        <section className="card wide" style={{ animationDelay: "0.25s" }}>
          <h2>Ask the Assistant</h2>
          <div className="field">
            <label>Question</label>
            <textarea
              rows={3}
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              placeholder="Ask about policy, SLA, product specifications, or escalation workflow..."
            />
          </div>
          <div className="actions">
            <button onClick={handleAsk} disabled={!isAuthenticated || !question}>
              Submit Query
            </button>
            <button className="ghost" onClick={handleRefreshApprovalResult} disabled={!approvalId}>
              Refresh Approval Result
            </button>
          </div>
          <div className="response">
            <div>
              <h3>Answer</h3>
              <p>{answer || "No answer yet."}</p>
              {approvalId && <p className="muted">Approval ID: {approvalId}</p>}
            </div>
            <div>
              <h3>Retrieved Context</h3>
              <ul>
                {retrieved.length === 0 && <li className="muted">No chunks retrieved.</li>}
                {retrieved.map((item, index) => (
                  <li key={index}>
                    <span className="score">{item.score.toFixed(3)}</span>
                    <span>{item.text}</span>
                    <span className="source">{item.source}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>

        <section className="card wide" style={{ animationDelay: "0.3s" }}>
          <div className="row">
            <div>
              <h2>Approvals</h2>
              <p className="muted">Human-in-the-loop governance for generated responses.</p>
            </div>
            <button className="ghost" onClick={handleLoadApprovals} disabled={!isAuthenticated || !canApprove}>
              Refresh
            </button>
          </div>
          <div className="field">
            <label>Decision Note</label>
            <input value={approvalNote} onChange={(event) => setApprovalNote(event.target.value)} />
          </div>
          {!canApprove && isAuthenticated && (
            <p className="muted">Admin or auditor role required to decide approvals.</p>
          )}
          <div className="approval-list">
            {approvals.length === 0 ? (
              <p className="muted">No pending approvals.</p>
            ) : (
              approvals.map((approval) => (
                <div className="approval-item" key={approval.approval_id}>
                  <div>
                    <p className="muted">{approval.approval_id}</p>
                    <p><strong>Question:</strong> {approval.question}</p>
                    <p><strong>Draft:</strong> {approval.draft_answer}</p>
                  </div>
                  <div className="actions">
                    <button onClick={() => handleDecision(approval, true)} disabled={!canApprove}>
                      Approve
                    </button>
                    <button className="ghost" onClick={() => handleDecision(approval, false)} disabled={!canApprove}>
                      Reject
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="card wide" style={{ animationDelay: "0.35s" }}>
          <div className="row">
            <div>
              <h2>Audit Trail</h2>
              <p className="muted">Tenant-aware audit records for compliance and investigations.</p>
            </div>
            <button className="ghost" onClick={handleAudit} disabled={!isAuthenticated}>
              Refresh
            </button>
          </div>
          <div className="audit">
            {auditLogs.length === 0 ? (
              <p className="muted">No audit logs loaded.</p>
            ) : (
              <table>
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Tenant</th>
                    <th>User</th>
                    <th>Action</th>
                    <th>Input</th>
                  </tr>
                </thead>
                <tbody>
                  {auditLogs.map((log) => (
                    <tr key={log.id}>
                      <td>{formatTimestamp(log.timestamp)}</td>
                      <td>{log.tenant_id}</td>
                      <td>{log.user}</td>
                      <td>{log.action}</td>
                      <td>{log.input_text}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </section>

        <section className="card wide" style={{ animationDelay: "0.4s" }}>
          <h2>Admin Console</h2>
          {!isAdmin && isAuthenticated && <p className="muted">Admin role required for user and tenant management.</p>}
          <div className="admin-grid">
            <div>
              <h3>Tenants</h3>
              <div className="row">
                <button className="ghost" onClick={handleLoadTenants} disabled={!isAdmin}>
                  Load Tenants
                </button>
              </div>
              <div className="field">
                <label>New Tenant Name</label>
                <input value={tenantName} onChange={(event) => setTenantName(event.target.value)} />
              </div>
              <button onClick={handleCreateTenant} disabled={!isAdmin || !tenantName}>
                Create Tenant
              </button>
              <ul className="list">
                {tenants.map((tenant) => (
                  <li key={tenant.tenant_id}>
                    {tenant.name} ({tenant.tenant_id})
                  </li>
                ))}
              </ul>
            </div>

            <div>
              <h3>Users</h3>
              <div className="row">
                <button className="ghost" onClick={handleLoadUsers} disabled={!isAdmin}>
                  Load Users
                </button>
              </div>
              <div className="field">
                <label>Username</label>
                <input value={newUserName} onChange={(event) => setNewUserName(event.target.value)} />
              </div>
              <div className="field">
                <label>Password</label>
                <input
                  type="password"
                  value={newUserPassword}
                  onChange={(event) => setNewUserPassword(event.target.value)}
                />
              </div>
              <div className="field">
                <label>Role</label>
                <select value={newUserRole} onChange={(event) => setNewUserRole(event.target.value)}>
                  <option value="admin">admin</option>
                  <option value="user">user</option>
                  <option value="auditor">auditor</option>
                </select>
              </div>
              <div className="field">
                <label>Default Tenant</label>
                <input
                  value={newUserDefaultTenant}
                  onChange={(event) => setNewUserDefaultTenant(event.target.value)}
                />
              </div>
              <button onClick={handleCreateUser} disabled={!isAdmin || !newUserName || !newUserPassword}>
                Create User
              </button>

              <div className="field">
                <label>Assign Tenant: User ID</label>
                <input value={assignUserId} onChange={(event) => setAssignUserId(event.target.value)} />
              </div>
              <div className="field">
                <label>Assign Tenant: Tenant ID</label>
                <input value={assignTenantId} onChange={(event) => setAssignTenantId(event.target.value)} />
              </div>
              <button onClick={handleAssignTenant} disabled={!isAdmin || !assignUserId || !assignTenantId}>
                Assign Tenant
              </button>

              <ul className="list">
                {users.map((userItem) => (
                  <li key={userItem.user_id}>
                    {userItem.username} ({userItem.role}) - tenants: {userItem.tenant_ids.join(", ") || "none"}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
