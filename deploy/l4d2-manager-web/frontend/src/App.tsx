import { FormEvent, ReactNode, RefObject, useEffect, useMemo, useRef, useState } from "react";

type Room = {
  id: string;
  label: string;
  service: string;
  port: number;
  active: string;
  sub_state: string;
  restarts: string;
  exit_status: string;
  started_at: string;
  default_map: string;
  default_campaign_id: string;
  port_listening: boolean;
};

type CampaignMap = {
  name: string;
  display_name: string;
  chapter: number;
};

type Campaign = {
  id: string;
  title: string;
  source: string;
  maps: CampaignMap[];
};

type Addon = {
  filename: string;
  state: string;
  size: number;
  modified_at: number;
  kind: string;
  maps: string[];
  missions: string[];
  source: string;
  catalog_id: string;
  title: string;
  url: string;
  install_ids: string[];
  package_status: string;
  reinstallable: boolean;
  group_id?: string;
  group_title?: string;
  group_members?: string[];
};

type Job = {
  id: string;
  type?: string;
  source?: string;
  kind?: string;
  status: string;
  stage?: string;
  message?: string;
  title?: string;
  catalog_id?: string;
  workshop_id?: string;
  export_filename?: string;
  download_url?: string;
  install_ids?: string[];
  progress?: number;
  progress_label?: string;
  downloaded_bytes?: number;
  total_bytes?: number;
  items_done?: number;
  items_total?: number;
};

type ServerPlugin = {
  id: string;
  label: string;
  filename?: string;
  state: string;
  size?: number;
};

type ServerPlugins = {
  metamod?: boolean;
  sourcemod?: boolean;
  plugins?: ServerPlugin[];
};

type SystemSnapshot = {
  cpu?: { cores?: number; percent?: number | null; load_average?: Array<number | null> };
  memory?: { total?: number; used?: number; available?: number; percent?: number | null };
  swap?: { total?: number; used?: number; free?: number; percent?: number | null };
  uptime?: { display?: string };
  disk?: Array<{ id: string; label: string; path: string; total?: number | null; used?: number | null; free?: number | null; percent?: number | null }>;
  processes?: Array<{ service: string; label?: string; active?: string; sub_state?: string; memory_current?: number | null; cpu_usage_nsec?: number | null }>;
};

type StateSnapshot = {
  generated_at: number;
  rooms: Room[];
  campaigns: Campaign[];
  maps: string[];
  addons: Addon[];
  jobs: Job[];
  server_plugins: ServerPlugins;
  system?: SystemSnapshot;
};

type CatalogItem = {
  source: string;
  id: string;
  install_ids?: string[];
  title: string;
  kind: string;
  url: string;
  size?: string;
  summary?: string;
  installable: boolean;
  reason?: string;
};

type PackageFilters = {
  text: string;
  status: string;
  source: string;
  record: string;
};

type ProxyItem = {
  ok: boolean;
  workshop_id: string;
  kind?: string;
  title?: string;
  file_url?: string;
  file_size?: number;
  suggested_filename?: string;
  message?: string;
};

type ProxyResolve = ProxyItem & {
  collection?: boolean;
  items?: ProxyItem[];
};

type WorkshopParts = {
  ok: boolean;
  workshop_id: string;
  kind?: string;
  collection?: boolean;
  title?: string;
  parts: ProxyItem[];
  message?: string;
};

const activeJobStatuses = new Set(["queued", "running"]);
const problemJobStatuses = new Set(["failed", "interrupted"]);

async function apiFetch(input: RequestInfo | URL, init: RequestInit = {}) {
  const response = await fetch(input, { credentials: "same-origin", ...init });
  if (response.status === 401) {
    window.location.href = "/login?expired=1";
    throw new Error("Session expired");
  }
  return response;
}

async function postForm<T = { ok: boolean; message?: string }>(path: string, fields: Record<string, string> | URLSearchParams) {
  const body = fields instanceof URLSearchParams ? fields : new URLSearchParams(fields);
  const response = await apiFetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body
  });
  const payload = (await response.json()) as T;
  return { response, payload };
}

function formatBytes(value?: number | null) {
  const size = Number(value || 0);
  if (!size) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let current = size;
  let unit = 0;
  while (current >= 1024 && unit < units.length - 1) {
    current /= 1024;
    unit += 1;
  }
  return unit === 0 ? `${current} ${units[unit]}` : `${current.toFixed(1)} ${units[unit]}`;
}

function formatPercent(value?: number | null) {
  return typeof value === "number" && Number.isFinite(value) ? `${value.toFixed(1)}%` : "unknown";
}

function riskClass(percent?: number | null, warn = 80, danger = 92) {
  if (typeof percent !== "number") return "";
  if (percent >= danger) return "danger";
  if (percent >= warn) return "warn";
  return "";
}

function statusClass(status: string) {
  if (["active", "enabled", "succeeded", "running"].includes(status)) return "ok";
  if (["queued", "remote", "disabled", "missing"].includes(status)) return "warn";
  if (["failed", "interrupted", "deleted", "inactive"].includes(status)) return "danger";
  return "";
}

function fileSizeMb(bytes: number) {
  if (!bytes) return "not downloaded";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function mapLabel(map: CampaignMap) {
  return `${map.chapter}. ${map.display_name} (${map.name})`;
}

const PART_SUFFIX_RE = /[\s_\-]*[(（]?\s*part\s*\d+\s*[)）]?\s*$/i;

function stripPartSuffix(title: string) {
  if (!title) return title;
  const stripped = title.replace(PART_SUFFIX_RE, "").trim();
  return stripped || title;
}

function selectedCampaignForRoom(room: Room, campaigns: Campaign[]) {
  if (room.default_campaign_id) return room.default_campaign_id;
  return campaigns[0]?.id || "";
}

function matchesPackageFilters(addon: Addon, filters: PackageFilters) {
  const source = addon.source || "local";
  const hasRecord = Boolean(addon.source && addon.catalog_id);
  if (filters.text) {
    const haystack = [addon.title, addon.filename, addon.catalog_id, addon.maps.join(" ")].join(" ").toLowerCase();
    if (!haystack.includes(filters.text.toLowerCase())) return false;
  }
  if (filters.status !== "all" && addon.state !== filters.status) return false;
  if (filters.source !== "all" && source !== filters.source) return false;
  if (filters.record === "with" && !hasRecord) return false;
  if (filters.record === "without" && hasRecord) return false;
  return true;
}

const navSections: Array<[string, string]> = [
  ["overview", "Overview"],
  ["performance", "Performance"],
  ["rooms", "Rooms"],
  ["install", "Install & Jobs"],
  ["packages", "Map Packages"],
  ["migration", "Migration"],
  ["mods", "Mods & Plugins"],
  ["maps", "Installed Maps"]
];

export default function App() {
  const [state, setState] = useState<StateSnapshot | null>(null);
  const [notice, setNotice] = useState("Loading...");
  const [catalogResults, setCatalogResults] = useState<CatalogItem[]>([]);
  const [jobFilter, setJobFilter] = useState("current");
  const [packageFilters, setPackageFilters] = useState<PackageFilters>({ text: "", status: "all", source: "all", record: "all" });
  const [selectedPackages, setSelectedPackages] = useState<Set<string>>(new Set());
  const [selectedManifest, setSelectedManifest] = useState<Set<string>>(new Set());
  const [autoRefresh, setAutoRefresh] = useState(true);
  const timer = useRef<number | undefined>();

  async function loadState(message = "Loading...") {
    setNotice(message);
    const response = await apiFetch("/api/state");
    if (!response.ok) throw new Error("Failed to load state");
    const data = (await response.json()) as StateSnapshot;
    setState(data);
    setNotice(`Updated ${new Date(data.generated_at * 1000).toLocaleString()}`);
  }

  useEffect(() => {
    loadState().catch((error) => setNotice(error.message));
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, []);

  useEffect(() => {
    if (!state) return;
    if (timer.current) window.clearTimeout(timer.current);
    const active = state.jobs.some((job) => activeJobStatuses.has(job.status));
    if (!autoRefresh && !active) return;
    timer.current = window.setTimeout(() => {
      loadState("Refreshing...").catch(() => undefined);
    }, active ? 2000 : 30000);
  }, [state, autoRefresh]);

  async function runAction(action: () => Promise<string | undefined>, loading: string) {
    setNotice(loading);
    try {
      const message = await action();
      if (message) setNotice(message);
      await loadState("Refreshing...");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Action failed");
    }
  }

  async function logout() {
    try {
      await apiFetch("/api/logout", { method: "POST" });
    } finally {
      window.location.href = "/login";
    }
  }

  if (!state) {
    return (
      <div className="shell boot">
        <div className="boot-card">
          <div className="brand-mark">L4D2</div>
          <h1>L4D2 Server Manager</h1>
          <p>{notice}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div className="topbar-main">
          <div>
            <div className="eyebrow">Dedicated server control plane</div>
            <h1>L4D2 Server Manager</h1>
          </div>
          <div className="top-actions">
            <span className="notice">{notice}</span>
            <label className="toggle">
              <input type="checkbox" checked={autoRefresh} onChange={(event) => setAutoRefresh(event.target.checked)} />
              Auto refresh
            </label>
            <button className="secondary" onClick={() => loadState("Refreshing...")}>Refresh</button>
            <button className="secondary" onClick={logout}>Logout</button>
          </div>
        </div>
        <nav className="section-nav">
          {navSections.map(([id, label]) => (
            <a key={id} href={`#${id}`}>{label}</a>
          ))}
        </nav>
      </header>
      <main>
        <section id="overview" className="anchor">
          <Overview state={state} />
        </section>
        <section id="performance" className="anchor">
          <SystemPanel system={state.system} />
        </section>
        <section id="rooms" className="anchor">
          <RoomsPanel state={state} runAction={runAction} />
        </section>
        <section id="install" className="anchor two-column">
          <InstallPanel
            results={catalogResults}
            setResults={setCatalogResults}
            setNotice={setNotice}
            loadState={loadState}
          />
          <JobsPanel jobs={state.jobs} jobFilter={jobFilter} setJobFilter={setJobFilter} runAction={runAction} />
        </section>
        <section id="packages" className="anchor">
          <PackagesPanel
            addons={state.addons}
            filters={packageFilters}
            setFilters={setPackageFilters}
            selectedPackages={selectedPackages}
            setSelectedPackages={setSelectedPackages}
            selectedManifest={selectedManifest}
            setSelectedManifest={setSelectedManifest}
            runAction={runAction}
            loadState={loadState}
            setNotice={setNotice}
          />
        </section>
        <section id="migration" className="anchor">
          <MigrationPanel
            selectedPackages={selectedPackages}
            selectedManifest={selectedManifest}
            runAction={runAction}
            loadState={loadState}
            setNotice={setNotice}
          />
        </section>
        <section id="mods" className="anchor two-column">
          <ModsPanel addons={state.addons} selectedManifest={selectedManifest} setSelectedManifest={setSelectedManifest} runAction={runAction} />
          <PluginsPanel plugins={state.server_plugins} runAction={runAction} />
        </section>
        <section id="maps" className="anchor">
          <CampaignPanel campaigns={state.campaigns} mapCount={state.maps.length} />
        </section>
      </main>
    </div>
  );
}

function Overview({ state }: { state: StateSnapshot }) {
  const roomsOnline = state.rooms.filter((room) => room.active === "active" && room.port_listening).length;
  const runningJobs = state.jobs.filter((job) => activeJobStatuses.has(job.status)).length;
  const problemJobs = state.jobs.filter((job) => problemJobStatuses.has(job.status)).length;
  const mapPackages = state.addons.filter((addon) => addon.kind === "map").length;
  const disabledMods = state.addons.filter((addon) => addon.kind !== "map" && addon.state === "disabled").length;
  const cards: Array<{ label: string; value: string | number; tone?: string; href?: string }> = [
    { label: "Rooms online", value: `${roomsOnline}/${state.rooms.length}`, tone: roomsOnline < state.rooms.length ? "warn" : "ok" },
    { label: "Running jobs", value: runningJobs, tone: runningJobs > 0 ? "live" : "" },
    { label: "Problem jobs", value: problemJobs, tone: problemJobs > 0 ? "danger" : "ok", href: problemJobs > 0 ? "#install" : undefined },
    { label: "Map packages", value: mapPackages },
    { label: "Disabled mods", value: disabledMods, tone: disabledMods > 0 ? "warn" : "" }
  ];
  return (
    <div className="overview-grid">
      {cards.map((card) => {
        const content = (
          <>
            <span>{card.label}</span>
            <strong>{card.value}</strong>
          </>
        );
        return card.href ? (
          <a className={`metric-card link ${card.tone || ""}`} key={card.label} href={card.href}>{content}</a>
        ) : (
          <article className={`metric-card ${card.tone || ""}`} key={card.label}>{content}</article>
        );
      })}
    </div>
  );
}

function Metric({ label, value, detail, percent, warn, danger }: { label: string; value: string; detail?: string; percent?: number | null; warn?: number; danger?: number }) {
  const bounded = typeof percent === "number" ? Math.max(0, Math.min(100, percent)) : null;
  return (
    <div className={`metric ${riskClass(percent, warn, danger)}`}>
      <span>{label}</span>
      <strong>{value}</strong>
      {detail && <small>{detail}</small>}
      {bounded !== null && <div className="bar"><i style={{ width: `${bounded}%` }} /></div>}
    </div>
  );
}

function SystemPanel({ system }: { system?: SystemSnapshot }) {
  if (!system) {
    return <section className="panel"><div className="empty-state">System metrics unavailable.</div></section>;
  }
  const cpu = system.cpu || {};
  const memory = system.memory || {};
  const swap = system.swap || {};
  const load = Array.isArray(cpu.load_average) ? cpu.load_average.filter((value) => value !== null).join(", ") : "unknown";
  return (
    <section className="panel">
      <PanelHead title="Server Performance" subtitle="Live host pressure, service process state, and storage health." badge="live" />
      <div className="metric-grid">
        <Metric label="CPU" value={formatPercent(cpu.percent)} detail={`${cpu.cores || 0} cores / load ${load || "unknown"}`} percent={cpu.percent} warn={75} danger={90} />
        <Metric label="Memory" value={`${formatBytes(memory.used)} / ${formatBytes(memory.total)}`} detail={`${formatBytes(memory.available)} available`} percent={memory.percent} warn={75} danger={90} />
        <Metric label="Swap" value={`${formatBytes(swap.used)} / ${formatBytes(swap.total)}`} detail={`${formatBytes(swap.free)} free`} percent={swap.percent} warn={40} danger={75} />
        <Metric label="Uptime" value={system.uptime?.display || "unknown"} />
      </div>
      <div className="process-grid">
        {(system.processes || []).map((proc) => (
          <div className="process-row" key={proc.service}>
            <div>
              <strong>{proc.label || proc.service}</strong>
              <small>{proc.service}</small>
            </div>
            <Pill label={proc.active || "unknown"} tone={proc.active === "active" ? "ok" : "warn"} />
            <span>{formatBytes(proc.memory_current)}</span>
            <span>{proc.cpu_usage_nsec ? `${Math.round(proc.cpu_usage_nsec / 1000000000)}s CPU` : "CPU unknown"}</span>
          </div>
        ))}
      </div>
      <div className="disk-grid">
        {(system.disk || []).map((disk) => (
          <Metric
            key={disk.id}
            label={`${disk.label} disk`}
            value={`${formatBytes(disk.used)} / ${formatBytes(disk.total)}`}
            detail={`${formatBytes(disk.free)} free at ${disk.path}`}
            percent={disk.percent}
          />
        ))}
      </div>
    </section>
  );
}

function RoomsPanel({ state, runAction }: { state: StateSnapshot; runAction: (action: () => Promise<string | undefined>, loading: string) => Promise<void> }) {
  const [roomMaps, setRoomMaps] = useState<Record<string, { campaignId: string; map: string }>>({});

  useEffect(() => {
    const next: Record<string, { campaignId: string; map: string }> = {};
    state.rooms.forEach((room) => {
      next[room.id] = {
        campaignId: selectedCampaignForRoom(room, state.campaigns),
        map: room.default_map
      };
    });
    setRoomMaps(next);
  }, [state]);

  function campaignMaps(roomId: string) {
    const campaign = state.campaigns.find((item) => item.id === roomMaps[roomId]?.campaignId) || state.campaigns[0];
    return campaign?.maps || [];
  }

  async function save(room: Room, restart: boolean) {
    const map = roomMaps[room.id]?.map || room.default_map;
    const { payload } = await postForm("/api/default-map", { room: room.id, map, restart: restart ? "1" : "0" });
    return payload.message;
  }

  async function restart(room: Room) {
    const { payload } = await postForm("/api/restart", { room: room.id });
    return payload.message;
  }

  return (
    <section>
      <PanelHead title="Room Management" subtitle="Save default maps without disconnecting players; restart actions interrupt the target room." />
      <div className="room-grid">
        {state.rooms.map((room) => {
          const online = room.active === "active" && room.port_listening;
          return (
            <article className="panel room-card" key={room.id}>
              <div className="card-title">
                <div>
                  <h3>{room.label}</h3>
                  <small>{room.service} / UDP {room.port}</small>
                </div>
                <Pill label={online ? "running" : room.active} tone={online ? "ok" : "danger"} />
              </div>
              <dl className="facts">
                <dt>Default map</dt><dd>{room.default_map || "unknown"}</dd>
                <dt>Port</dt><dd>{room.port_listening ? "listening" : "not listening"}</dd>
                <dt>Sub-state</dt><dd>{room.sub_state}</dd>
                <dt>Restarts</dt><dd>{room.restarts}</dd>
                <dt>Started</dt><dd>{room.started_at || "unknown"}</dd>
              </dl>
              <div className="control-row">
                <select
                  value={roomMaps[room.id]?.campaignId || ""}
                  onChange={(event) => {
                    const campaign = state.campaigns.find((item) => item.id === event.target.value);
                    setRoomMaps((current) => ({ ...current, [room.id]: { campaignId: event.target.value, map: campaign?.maps[0]?.name || "" } }));
                  }}
                >
                  {state.campaigns.map((campaign) => <option value={campaign.id} key={campaign.id}>{campaign.title}</option>)}
                </select>
                <select
                  value={roomMaps[room.id]?.map || ""}
                  onChange={(event) => setRoomMaps((current) => ({ ...current, [room.id]: { ...current[room.id], map: event.target.value } }))}
                >
                  {campaignMaps(room.id).map((map) => <option value={map.name} key={map.name}>{mapLabel(map)}</option>)}
                </select>
              </div>
              <div className="actions">
                <button onClick={() => runAction(() => save(room, false), "Saving default map...")}>Save</button>
                <button className="danger" onClick={() => window.confirm(`Restart ${room.label}? Current players may disconnect.`) && runAction(() => save(room, true), "Saving and restarting...")}>Save + Restart</button>
                <button className="secondary" onClick={() => window.confirm(`Restart ${room.label}? Current players may disconnect.`) && runAction(() => restart(room), "Restarting room...")}>Restart</button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function InstallPanel({ results, setResults, setNotice, loadState }: {
  results: CatalogItem[];
  setResults: (items: CatalogItem[]) => void;
  setNotice: (message: string) => void;
  loadState: (message?: string) => Promise<void>;
}) {
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("map");
  const [workshopId, setWorkshopId] = useState("");
  const [workshopKind, setWorkshopKind] = useState("map");
  const [submitting, setSubmitting] = useState("");
  const [proxyResolve, setProxyResolve] = useState<ProxyResolve | null>(null);
  const localFile = useRef<HTMLInputElement>(null);
  const [localKind, setLocalKind] = useState("map");
  const [localId, setLocalId] = useState("");
  const [localParts, setLocalParts] = useState<WorkshopParts | null>(null);
  const [localFiles, setLocalFiles] = useState<Array<{ file: File; pick: string }>>([]);

  async function search() {
    setNotice("Searching catalog...");
    const response = await apiFetch(`/api/catalog/search?${new URLSearchParams({ query, kind })}`);
    const payload = await response.json();
    if (!response.ok) {
      setNotice(payload.message || "Search failed");
      return;
    }
    setResults(payload.results || []);
    setNotice(`${(payload.results || []).length} result(s)`);
  }

  async function installWorkshop() {
    if (submitting) return;
    setSubmitting("Submitting Workshop install request...");
    setNotice("Queueing Workshop install...");
    try {
      const { payload } = await postForm("/api/workshop/install", { kind: workshopKind, workshop_id: workshopId.trim() });
      setNotice(payload.message || "Install queued");
      await loadState("Refreshing...");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to submit install request");
    } finally {
      setSubmitting("");
    }
  }

  async function installCatalog(item: CatalogItem) {
    if (submitting) return;
    setSubmitting(`Submitting install request for ${item.title}...`);
    setNotice("Queueing catalog install...");
    try {
      const { payload } = await postForm("/api/catalog/install", {
        source: item.source,
        kind: item.kind,
        id: item.id,
        title: item.title,
        url: item.url,
        install_ids: (item.install_ids || []).join(",")
      });
      setNotice(payload.message || "Install queued");
      await loadState("Refreshing...");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Failed to submit install request");
    } finally {
      setSubmitting("");
    }
  }

  async function resolveProxy(id: string, proxyKind: string) {
    if (submitting) return;
    const trimmed = id.trim();
    if (!trimmed) {
      setNotice("Enter a Workshop ID first.");
      return;
    }
    setSubmitting("Resolving Steam download links...");
    setNotice("Resolving Workshop download links...");
    try {
      const response = await apiFetch(`/api/workshop/resolve?${new URLSearchParams({ workshop_id: trimmed, kind: proxyKind })}`);
      const payload = (await response.json()) as ProxyResolve & { message?: string };
      if (!response.ok || !payload.ok) {
        setProxyResolve(null);
        setNotice(payload.message || "Failed to resolve download links");
        return;
      }
      setProxyResolve(payload);
      setNotice("Proxy download ready — download on your machine, then upload to install.");
    } catch (error) {
      setProxyResolve(null);
      setNotice(error instanceof Error ? error.message : "Failed to resolve download links");
    } finally {
      setSubmitting("");
    }
  }

  async function installLocalFile(file: File | undefined, uploadKind: string) {
    if (submitting) return;
    if (!file) {
      setNotice("Select a .vpk file first.");
      return;
    }
    setSubmitting(`Uploading ${file.name}...`);
    setNotice("Uploading and installing...");
    try {
      const form = new FormData();
      form.append("file", file);
      form.append("kind", uploadKind);
      const response = await apiFetch("/api/upload", { method: "POST", body: form });
      const payload = await response.json();
      setNotice(payload.message || (response.ok ? "Uploaded" : "Upload failed"));
      if (response.ok) await loadState("Refreshing...");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Upload failed");
    } finally {
      setSubmitting("");
    }
  }

  async function resolveLocalParts() {
    if (submitting) return;
    const trimmed = localId.trim();
    if (!trimmed) {
      setNotice("Enter a Workshop ID first.");
      return;
    }
    setSubmitting("Resolving Workshop parts...");
    setNotice("Resolving parts that belong to this Workshop ID...");
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 30000);
    try {
      const response = await apiFetch(`/api/workshop/parts?${new URLSearchParams({ workshop_id: trimmed, kind: localKind })}`, { signal: controller.signal });
      const payload = (await response.json()) as WorkshopParts;
      if (!response.ok || !payload.ok) {
        setLocalParts(null);
        setLocalFiles([]);
        setNotice(payload.message || "Failed to resolve parts");
        return;
      }
      setLocalParts(payload);
      setLocalFiles([]);
      const usable = (payload.parts || []).filter((p) => p.ok);
      setNotice(`${usable.length} downloadable part(s) found — choose your .vpk file(s) to auto-match by size.`);
    } catch (error) {
      setLocalParts(null);
      if (error instanceof DOMException && error.name === "AbortError") {
        setNotice("Resolve timed out — Steam may be unreachable from the server. Try again, or use 'Install ID' / 'Proxy download'.");
      } else {
        setNotice(error instanceof Error ? error.message : "Failed to resolve parts");
      }
    } finally {
      window.clearTimeout(timeout);
      setSubmitting("");
    }
  }

  function autoMatchPick(size: number) {
    if (!localParts) return "";
    const matches = (localParts.parts || []).filter((p) => p.ok && Number(p.file_size || 0) === size);
    return matches.length === 1 ? String(matches[0].workshop_id) : "";
  }

  function onLocalFilesChange(files: File[]) {
    if (!localParts) {
      setLocalFiles(files.map((file) => ({ file, pick: "" })));
      return;
    }
    const next = files.map((file) => ({ file, pick: autoMatchPick(file.size) }));
    setLocalFiles(next);
    const auto = next.filter((entry) => entry.pick).length;
    setNotice(`${files.length} file(s) selected · ${auto} auto-matched by size · resolve the rest manually if needed.`);
  }

  function setFilePick(index: number, pick: string) {
    setLocalFiles((prev) => prev.map((entry, i) => (i === index ? { ...entry, pick } : entry)));
  }

  async function uploadWorkshopFiles() {
    if (submitting) return;
    if (!localParts) {
      setNotice("Resolve the Workshop ID parts first.");
      return;
    }
    if (!localFiles.length) {
      setNotice("Select one or more .vpk files first.");
      return;
    }
    let done = 0;
    const failures: string[] = [];
    for (let i = 0; i < localFiles.length; i += 1) {
      const { file, pick } = localFiles[i];
      setSubmitting(`Uploading ${file.name} (${i + 1}/${localFiles.length})...`);
      setNotice(`Verifying and installing ${file.name}...`);
      try {
        const form = new FormData();
        form.append("file", file);
        form.append("kind", localKind);
        form.append("workshop_id", localParts.workshop_id);
        if (pick) form.append("expected_id", pick);
        const response = await apiFetch("/api/upload/workshop", { method: "POST", body: form });
        const payload = await response.json();
        if (response.ok) {
          done += 1;
        } else {
          failures.push(`${file.name}: ${payload.message || "failed"}`);
        }
      } catch (error) {
        failures.push(`${file.name}: ${error instanceof Error ? error.message : "failed"}`);
      }
    }
    setSubmitting("");
    if (failures.length) {
      setNotice(`Installed ${done}/${localFiles.length}. Failed: ${failures.join("; ")}`);
    } else {
      setNotice(`Installed ${done}/${localFiles.length} file(s).`);
      setLocalParts(null);
      setLocalFiles([]);
      if (localFile.current) localFile.current.value = "";
    }
    await loadState("Refreshing...");
  }

  return (
    <section className="panel">
      {submitting && (
        <div className="busy-overlay" role="alert" aria-busy="true">
          <div className="busy-card">
            <span className="busy-spinner" aria-hidden="true" />
            <span className="busy-text">{submitting}</span>
            <span className="busy-hint">Please wait — do not click again.</span>
          </div>
        </div>
      )}
      <PanelHead title="Install Maps and Mods" subtitle="Search Workshop/GameMaps candidates or install a known Workshop ID directly." badge="Workshop / GameMaps" />
      <form className="tool-row" onSubmit={(event) => { event.preventDefault(); search(); }}>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Run To The Hills" />
        <select value={kind} onChange={(event) => setKind(event.target.value)}>
          <option value="map">Map</option>
          <option value="mod">Mod</option>
        </select>
        <button type="submit">Search</button>
      </form>
      <div className="tool-row">
        <input value={workshopId} onChange={(event) => setWorkshopId(event.target.value)} inputMode="numeric" placeholder="Workshop ID" />
        <select value={workshopKind} onChange={(event) => setWorkshopKind(event.target.value)}>
          <option value="map">Map</option>
          <option value="mod">Mod</option>
        </select>
        <button onClick={installWorkshop} disabled={Boolean(submitting)}>Install ID</button>
        <button className="secondary" onClick={() => resolveProxy(workshopId, workshopKind)} disabled={Boolean(submitting)}>Proxy download</button>
      </div>
      {proxyResolve && (
        <ProxyDownloadCard
          resolve={proxyResolve}
          submitting={Boolean(submitting)}
          onClose={() => setProxyResolve(null)}
          onInstallFile={installLocalFile}
        />
      )}
      <div className="tool-card proxy-local">
        <h3>Smart local install (verified against a Workshop ID)</h3>
        <p>Have a matching <code>.vpk</code> on your machine? Enter the Workshop ID, then choose the file — the server resolves which parts belong to that ID and verifies your file by exact byte size before installing it under that ID.</p>
        <div className="tool-row">
          <input
            value={localId}
            onChange={(event) => { setLocalId(event.target.value); setLocalParts(null); setLocalFiles([]); }}
            inputMode="numeric"
            placeholder="Workshop ID"
          />
          <select value={localKind} onChange={(event) => { setLocalKind(event.target.value); setLocalParts(null); setLocalFiles([]); }}>
            <option value="map">Map package</option>
            <option value="mod">Mod</option>
          </select>
          <button className="secondary" disabled={Boolean(submitting)} onClick={resolveLocalParts}>Resolve parts</button>
        </div>
        {localParts && (
          <>
            <div className="proxy-list">
              {(localParts.parts || []).map((part, index) => {
                const usable = part.ok && Number(part.file_size || 0) > 0;
                const matched = usable && localFiles.some((entry) => Number(part.file_size || 0) === entry.file.size);
                return (
                  <div className={`proxy-item${matched ? " matched" : ""}`} key={`${part.workshop_id || index}`}>
                    <div className="proxy-meta">
                      <strong>{part.title || `Workshop ${part.workshop_id}`}</strong>
                      <div className="muted mono">
                        {part.workshop_id}
                        {part.file_size ? ` · ${formatBytes(part.file_size)}` : ""}
                      </div>
                      {!part.ok && <small>{part.message || "Could not resolve this item"}</small>}
                    </div>
                    {matched && <Pill label="size match" tone="ok" />}
                  </div>
                );
              })}
            </div>
            <div className="actions">
              <FileField inputRef={localFile} accept=".vpk" label="Choose VPK file(s)" multiple onChangeFiles={onLocalFilesChange} />
              <button disabled={Boolean(submitting) || !localFiles.length} onClick={uploadWorkshopFiles}>
                Verify &amp; install{localFiles.length > 1 ? ` (${localFiles.length})` : ""}
              </button>
            </div>
            {localFiles.length > 0 && (
              <div className="proxy-list">
                {localFiles.map((entry, index) => {
                  const auto = autoMatchPick(entry.file.size);
                  return (
                    <div className="proxy-item" key={`${entry.file.name}-${index}`}>
                      <div className="proxy-meta">
                        <strong>{entry.file.name}</strong>
                        <div className="muted mono">{formatBytes(entry.file.size)}</div>
                      </div>
                      <div className="actions right">
                        {entry.pick
                          ? <Pill label={auto && auto === entry.pick ? "auto-matched" : "manual"} tone="ok" />
                          : <Pill label="no match" tone="warn" />}
                        <select value={entry.pick} onChange={(event) => setFilePick(index, event.target.value)}>
                          <option value="">Auto / unmatched</option>
                          {(localParts.parts || []).filter((p) => p.ok).map((p) => (
                            <option value={String(p.workshop_id)} key={String(p.workshop_id)}>
                              {p.workshop_id} · {formatBytes(p.file_size)}
                            </option>
                          ))}
                        </select>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
      <div className="result-list">
        {!results.length && <div className="empty-state">Search results will appear here.</div>}
        {results.map((item) => (
          <article className="result-item" key={`${item.source}-${item.id}`}>
            <div>
              <strong>{item.title}</strong>
              <div className="muted mono">{item.kind} / {item.source} {item.id}</div>
              {item.install_ids && item.install_ids.length > 1 && <div className="muted mono">packages {item.install_ids.join(", ")}</div>}
              {item.summary && <p>{item.summary}</p>}
              {item.reason && <small>{item.reason}</small>}
            </div>
            <div className="actions right">
              {item.size && <Pill label={item.size} />}
              <a href={item.url} target="_blank" rel="noreferrer">Open</a>
              {item.source === "workshop" && (
                <button className="secondary" disabled={Boolean(submitting)} onClick={() => resolveProxy(item.id, item.kind)}>Proxy</button>
              )}
              <button disabled={!item.installable || Boolean(submitting)} onClick={() => installCatalog(item)}>Install</button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}

function ProxyDownloadCard({ resolve, submitting, onClose, onInstallFile }: {
  resolve: ProxyResolve;
  submitting: boolean;
  onClose: () => void;
  onInstallFile: (file: File | undefined, kind: string) => Promise<void>;
}) {
  const items: ProxyItem[] = resolve.collection ? (resolve.items || []) : [resolve as ProxyItem];
  const downloadable = items.filter((entry) => entry.ok && entry.file_url);
  return (
    <div className="tool-card proxy-card">
      <div className="proxy-head">
        <h3>Proxy download {resolve.collection ? `(collection · ${items.length} parts)` : ""}</h3>
        <button className="secondary" onClick={onClose}>Close</button>
      </div>
      <p>Steam downloads run through <strong>your machine</strong>: ① download the file locally, then ② select it to upload &amp; install on the server. Use this when the server cannot reach Steam reliably.</p>
      <div className="proxy-list">
        {!downloadable.length && <div className="empty-state">No downloadable file_url returned (item may be restricted).</div>}
        {items.map((entry, index) => (
          <div className="proxy-item" key={`${entry.workshop_id || index}`}>
            <div className="proxy-meta">
              <strong>{entry.title || `Workshop ${entry.workshop_id}`}</strong>
              <div className="muted mono">
                {entry.suggested_filename || entry.workshop_id}
                {entry.file_size ? ` · ${formatBytes(entry.file_size)}` : ""}
              </div>
              {!entry.ok && <small>{entry.message || "Could not resolve this item"}</small>}
            </div>
            {entry.ok && entry.file_url && (
              <div className="actions right">
                <a className="proxy-step" href={entry.file_url} target="_blank" rel="noreferrer" download={entry.suggested_filename}>① Download</a>
                <label className="file-field proxy-step">
                  <span className="file-button">② Select &amp; install</span>
                  <input
                    type="file"
                    accept=".vpk"
                    disabled={submitting}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      event.target.value = "";
                      onInstallFile(file, entry.kind || resolve.kind || "map");
                    }}
                  />
                </label>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function JobsPanel({ jobs, jobFilter, setJobFilter, runAction }: {
  jobs: Job[];
  jobFilter: string;
  setJobFilter: (value: string) => void;
  runAction: (action: () => Promise<string | undefined>, loading: string) => Promise<void>;
}) {
  const currentJobs = jobs.filter((job) => activeJobStatuses.has(job.status) || problemJobStatuses.has(job.status));
  const problemJobs = jobs.filter((job) => problemJobStatuses.has(job.status));
  const historyJobs = jobs.filter((job) => job.status === "succeeded");
  const filtered = jobFilter === "current" ? currentJobs : jobFilter === "problem" ? problemJobs : jobFilter === "history" ? historyJobs.slice(0, 8) : jobs;

  async function cancel(job: Job) {
    const { payload } = await postForm("/api/job/cancel", { job_id: job.id });
    return payload.message;
  }

  async function remove(job: Job) {
    if (!window.confirm("Delete this job record? This only removes the history entry.")) return "Delete cancelled";
    const { payload } = await postForm("/api/job/delete", { job_id: job.id });
    return payload.message;
  }

  async function rerun(job: Job) {
    const { payload } = await postForm("/api/job/rerun", { job_id: job.id });
    return payload.message;
  }

  return (
    <section className="panel">
      <PanelHead title="Jobs" subtitle="Install, export, import, and plugin tasks with active failures kept visible." badge={`${currentJobs.length} current`} />
      <Segmented value={jobFilter} setValue={setJobFilter} options={[["current", "Current"], ["problem", "Failed"], ["history", "History"], ["all", "All"]]} />
      <div className="job-list">
        {!filtered.length && <div className="empty-state">No jobs match this filter.</div>}
        {filtered.map((job) => {
          const active = activeJobStatuses.has(job.status);
          const canRerun = !active && (job.source === "workshop" || job.source === "gamemaps") && Boolean(job.catalog_id || job.workshop_id);
          return (
            <article className={`job-card ${statusClass(job.status)}`} key={job.id}>
              <div className="card-title">
                <div>
                  <h3>{job.title || job.catalog_id || job.workshop_id || job.export_filename || job.id}</h3>
                  <small>{job.type || job.source || "task"} {job.kind || ""} / {job.stage || "done"}</small>
                </div>
                <Pill label={job.status} tone={statusClass(job.status)} />
              </div>
              {(active || typeof job.progress === "number") && <JobProgress job={job} active={active} />}
              {job.install_ids && job.install_ids.length > 1 && <div className="muted mono">packages {job.install_ids.join(", ")}</div>}
              {job.message && <JobMessage message={job.message} />}
              <div className="actions">
                {active && <button className="secondary" onClick={() => runAction(() => cancel(job), "Cancelling job...")}>Cancel</button>}
                {canRerun && <button onClick={() => runAction(() => rerun(job), "Re-running install...")}>Re-run</button>}
                {job.type === "export" && job.status === "succeeded" && job.download_url && <a href={job.download_url}>Download</a>}
                {!active && <button className="danger" onClick={() => runAction(() => remove(job), "Deleting job...")}>Delete</button>}
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function JobProgress({ job, active }: { job: Job; active: boolean }) {
  const percent = Math.max(0, Math.min(100, Number(job.progress || 0)));
  const downloaded = Number(job.downloaded_bytes || 0);
  const total = Number(job.total_bytes || 0);
  const sample = useRef<{ bytes: number; time: number } | null>(null);
  const [speed, setSpeed] = useState(0);

  useEffect(() => {
    if (!active) {
      sample.current = null;
      setSpeed(0);
      return;
    }
    const now = Date.now();
    const prev = sample.current;
    if (prev && downloaded > prev.bytes && now > prev.time) {
      const rate = ((downloaded - prev.bytes) * 1000) / (now - prev.time);
      setSpeed(rate);
    } else if (prev && downloaded < prev.bytes) {
      setSpeed(0);
    }
    sample.current = { bytes: downloaded, time: now };
  }, [downloaded, active]);

  const itemsTotal = Number(job.items_total || 0);
  const itemsDone = Number(job.items_done || 0);
  return (
    <div className="job-progress">
      <div className="bar"><i style={{ width: `${percent}%` }} /></div>
      <div className="progress-meta mono">
        <span>{percent}%</span>
        {total > 0 && <span>{formatBytes(downloaded)} / {formatBytes(total)}</span>}
        {active && speed > 0 && <span>{formatBytes(speed)}/s</span>}
        {itemsTotal > 1 && <span>part {Math.min(itemsTotal, itemsDone + (active ? 1 : 0))}/{itemsTotal}</span>}
      </div>
    </div>
  );
}

function JobMessage({ message }: { message: string }) {
  const trimmed = message.trim();
  const lines = trimmed.split(/\r?\n/);
  const isMultiline = lines.length > 1 || trimmed.length > 160;
  if (!isMultiline) {
    return <p className="job-summary">{trimmed}</p>;
  }
  const summary = (lines.find((line) => /error|failed|exception|traceback/i.test(line)) || lines[lines.length - 1] || lines[0]).trim();
  return (
    <details className="job-detail">
      <summary><span className="job-summary">{summary.slice(0, 200)}</span><span className="more">Details</span></summary>
      <pre>{trimmed}</pre>
    </details>
  );
}

function PackagesPanel(props: {
  addons: Addon[];
  filters: PackageFilters;
  setFilters: (value: PackageFilters) => void;
  selectedPackages: Set<string>;
  setSelectedPackages: (value: Set<string>) => void;
  selectedManifest: Set<string>;
  setSelectedManifest: (value: Set<string>) => void;
  runAction: (action: () => Promise<string | undefined>, loading: string) => Promise<void>;
  loadState: (message?: string) => Promise<void>;
  setNotice: (message: string) => void;
}) {
  const packages = props.addons.filter((addon) => addon.kind === "map");
  const filtered = packages.filter((addon) => matchesPackageFilters(addon, props.filters));
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const [regrouping, setRegrouping] = useState(false);

  type PackageGroup = { key: string; title: string; members: Addon[] };
  const groups: PackageGroup[] = [];
  const groupIndex = new Map<string, number>();
  for (const addon of filtered) {
    const key = addon.group_id || addon.catalog_id || addon.filename;
    if (groupIndex.has(key)) {
      groups[groupIndex.get(key)!].members.push(addon);
    } else {
      groupIndex.set(key, groups.length);
      groups.push({ key, title: addon.group_title || "", members: [addon] });
    }
  }

  function toggleExpanded(key: string) {
    const next = new Set(expanded);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setExpanded(next);
  }

  async function regroup() {
    setRegrouping(true);
    props.setNotice("Rebuilding map groups...");
    try {
      const { payload } = await postForm("/api/map-package/regroup", {});
      props.setNotice(payload.message || "Map groups rebuilt.");
      await props.loadState("Refreshing...");
    } catch (error) {
      props.setNotice(error instanceof Error ? error.message : "Regroup failed");
    } finally {
      setRegrouping(false);
    }
  }

  function updateFilters(partial: Partial<PackageFilters>) {
    props.setFilters({ ...props.filters, ...partial });
  }

  function toggle(setter: (value: Set<string>) => void, current: Set<string>, filename: string, checked: boolean) {
    const next = new Set(current);
    if (checked) next.add(filename);
    else next.delete(filename);
    setter(next);
  }

  async function addonState(addon: Addon) {
    const target = addon.state === "enabled" ? "disabled" : "enabled";
    const { payload } = await postForm("/api/addon/state", { filename: addon.filename, state: target });
    return payload.message;
  }

  async function deletePackage(addon: Addon, mode: "soft" | "purge") {
    const copy = mode === "purge"
      ? `Permanently delete ${addon.filename}? This removes local files and source records.`
      : `Delete local files for ${addon.filename}? Source records are kept for reinstall.`;
    if (!window.confirm(copy)) return "Delete cancelled";
    const { payload } = await postForm("/api/map-package/delete", { filename: addon.filename, mode });
    return payload.message;
  }

  async function reinstall(addon: Addon) {
    const { payload } = await postForm("/api/map-package/reinstall", { filename: addon.filename });
    return payload.message;
  }

  async function installManifest(addon: Addon) {
    const { payload } = await postForm("/api/manifest/install", { filename: addon.filename });
    return payload.message;
  }

  async function removeManifest(addon: Addon) {
    if (!window.confirm(`Remove source record for ${addon.filename}? Local VPK files are not deleted.`)) return "Remove cancelled";
    const { payload } = await postForm("/api/manifest/remove-record", { filename: addon.filename });
    return payload.message;
  }

  async function exportOne(addon: Addon) {
    const body = new URLSearchParams();
    body.append("filename", addon.filename);
    const { payload } = await postForm("/api/map-package/export-job", body);
    return payload.message;
  }

  function renderRow(addon: Addon) {
    const remote = addon.state === "remote";
    const deleted = addon.state === "deleted";
    const baseTitle = addon.title && addon.title !== addon.filename ? stripPartSuffix(addon.title) : addon.filename;
    const idHint = addon.source && addon.catalog_id ? `${addon.source} ${addon.catalog_id}` : "local package";
    return (
      <article className="package-row" key={addon.filename}>
        <div className="check-stack">
          <label><input type="checkbox" checked={props.selectedManifest.has(addon.filename)} onChange={(event) => toggle(props.setSelectedManifest, props.selectedManifest, addon.filename, event.target.checked)} /> Manifest</label>
          {!remote && !deleted && <label><input type="checkbox" checked={props.selectedPackages.has(addon.filename)} onChange={(event) => toggle(props.setSelectedPackages, props.selectedPackages, addon.filename, event.target.checked)} /> ZIP</label>}
        </div>
        <div>
          <strong>{baseTitle}</strong>
          <div className="muted mono">{addon.filename}</div>
          <div className="muted mono">{addon.maps.length ? addon.maps.join(", ") : "mission only"}</div>
        </div>
        <Pill label={addon.state} tone={statusClass(addon.state)} />
        <span>{remote ? "not downloaded" : deleted ? "removed" : fileSizeMb(addon.size)}</span>
        <span className="muted">{idHint}</span>
        <div className="actions right">
          {addon.url && <a href={addon.url} target="_blank" rel="noreferrer">Open</a>}
          {!remote && !deleted && <button className="secondary" onClick={() => props.runAction(() => exportOne(addon), "Queueing export...")}>Export ZIP</button>}
          {addon.reinstallable && !remote && <button onClick={() => props.runAction(() => reinstall(addon), "Queueing reinstall...")}>Reinstall</button>}
          {remote && addon.reinstallable && <button onClick={() => props.runAction(() => installManifest(addon), "Queueing source install...")}>Install Source</button>}
          {remote && <button className="secondary" onClick={() => props.runAction(() => removeManifest(addon), "Removing source record...")}>Remove Record</button>}
          {!deleted && !remote && <button className="secondary" onClick={() => props.runAction(() => addonState(addon), "Updating package state...")}>{addon.state === "enabled" ? "Disable" : "Enable"}</button>}
          {!deleted && (
            <RowMenu>
              {!remote && <button className="menu-item danger" onClick={() => props.runAction(() => deletePackage(addon, "soft"), "Deleting local files...")}>Delete Local</button>}
              <button className="menu-item danger" onClick={() => props.runAction(() => deletePackage(addon, "purge"), "Purging package...")}>Purge</button>
            </RowMenu>
          )}
        </div>
      </article>
    );
  }

  function groupTone(members: Addon[]) {
    if (members.some((m) => m.state === "remote")) return "warn";
    if (members.some((m) => m.state === "disabled")) return "warn";
    if (members.some((m) => m.state === "deleted")) return "danger";
    return "ok";
  }

  function groupStateLabel(members: Addon[]) {
    if (members.some((m) => m.state === "remote")) return "missing parts";
    if (members.some((m) => m.state === "disabled")) return "mixed";
    if (members.some((m) => m.state === "deleted")) return "deleted";
    return "enabled";
  }

  return (
    <section className="panel">
      <PanelHead title="Map Packages" subtitle="Filter installed and recorded packages; deletion keeps source records unless purged." badge={`${filtered.length}/${packages.length} visible`} />
      <div className="filter-row">
        <input value={props.filters.text} onChange={(event) => updateFilters({ text: event.target.value })} placeholder="Filter title, file, map, or source ID" />
        <select value={props.filters.status} onChange={(event) => updateFilters({ status: event.target.value })}>
          <option value="all">All states</option>
          <option value="enabled">Enabled</option>
          <option value="disabled">Disabled</option>
          <option value="remote">Remote</option>
          <option value="deleted">Deleted</option>
        </select>
        <select value={props.filters.source} onChange={(event) => updateFilters({ source: event.target.value })}>
          <option value="all">All sources</option>
          <option value="workshop">Workshop</option>
          <option value="gamemaps">GameMaps</option>
          <option value="local">Local</option>
        </select>
        <select value={props.filters.record} onChange={(event) => updateFilters({ record: event.target.value })}>
          <option value="all">All records</option>
          <option value="with">Has source record</option>
          <option value="without">No source record</option>
        </select>
        <button className="secondary" disabled={regrouping} onClick={regroup}>{regrouping ? "Rebuilding..." : "Rebuild groups"}</button>
      </div>
      <div className="package-list">
        {!filtered.length && <div className="empty-state">No map packages match this filter.</div>}
        {groups.map((group) => {
          if (group.members.length <= 1) {
            return renderRow(group.members[0]);
          }
          const open = expanded.has(group.key);
          const totalSize = group.members.reduce((sum, m) => sum + (m.size || 0), 0);
          const groupTitle = group.title || stripPartSuffix(group.members[0].title) || group.members[0].filename;
          return (
            <div className={`package-group ${open ? "open" : ""}`} key={group.key}>
              <button type="button" className="package-group-head" onClick={() => toggleExpanded(group.key)}>
                <span className="group-arrow">{open ? "\u25be" : "\u25b8"}</span>
                <div className="group-meta">
                  <strong>{groupTitle}</strong>
                  <div className="muted mono">workshop {group.key} · {group.members.length} parts</div>
                </div>
                <Pill label={groupStateLabel(group.members)} tone={groupTone(group.members)} />
                <span>{fileSizeMb(totalSize)}</span>
              </button>
              {open && <div className="package-group-body">{group.members.map((member) => renderRow(member))}</div>}
            </div>
          );
        })}
      </div>
    </section>
  );
}

function MigrationPanel({ selectedPackages, selectedManifest, loadState, setNotice }: {
  selectedPackages: Set<string>;
  selectedManifest: Set<string>;
  runAction: (action: () => Promise<string | undefined>, loading: string) => Promise<void>;
  loadState: (message?: string) => Promise<void>;
  setNotice: (message: string) => void;
}) {
  const manifestFile = useRef<HTMLInputElement>(null);
  const zipFile = useRef<HTMLInputElement>(null);
  const vpkFile = useRef<HTMLInputElement>(null);
  const [vpkKind, setVpkKind] = useState("map");

  async function exportManifest() {
    if (!selectedManifest.size) {
      setNotice("Select at least one manifest record.");
      return;
    }
    setNotice("Preparing manifest...");
    const body = new URLSearchParams();
    selectedManifest.forEach((filename) => body.append("filename", filename));
    const response = await apiFetch("/api/manifest/export", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body });
    if (!response.ok) {
      const payload = await response.json();
      setNotice(payload.message || "Manifest export failed");
      return;
    }
    downloadBlob(response, "l4d2-manager-manifest.json");
    setNotice("Manifest exported.");
  }

  async function exportZip() {
    if (!selectedPackages.size) {
      setNotice("Select at least one installed map package for ZIP export.");
      return;
    }
    setNotice("Queueing ZIP export...");
    const body = new URLSearchParams();
    selectedPackages.forEach((filename) => body.append("filename", filename));
    const { payload } = await postForm("/api/map-package/export-job", body);
    setNotice(payload.message || "Export queued");
    await loadState("Refreshing...");
  }

  async function upload(path: string, file: File | undefined, kind?: string) {
    if (!file) {
      setNotice("Select a file first.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    if (kind) form.append("kind", kind);
    setNotice("Uploading...");
    const response = await apiFetch(path, { method: "POST", body: form });
    const payload = await response.json();
    setNotice(payload.message || (response.ok ? "Uploaded" : "Upload failed"));
    if (response.ok) await loadState("Refreshing...");
  }

  return (
    <section className="panel">
      <PanelHead title="Migration" subtitle="Prefer source manifests; use ZIP when sources are unavailable; use VPK for emergency single-file imports." badge="Manifest / ZIP / VPK" />
      <div className="migration-grid">
        <div className="tool-card">
          <h3>Source manifest</h3>
          <p>Moves source records and reinstall metadata without transferring large VPK files.</p>
          <div className="actions">
            <button onClick={exportManifest}>Export selected records</button>
            <FileField inputRef={manifestFile} accept=".json,application/json" label="Choose JSON" />
            <button className="secondary" onClick={() => upload("/api/manifest/import", manifestFile.current?.files?.[0])}>Import records</button>
          </div>
        </div>
        <div className="tool-card">
          <h3>Complete ZIP</h3>
          <p>Transfers VPK files and metadata when sources are missing or the target cannot reach the internet.</p>
          <div className="actions">
            <button className="secondary" onClick={exportZip}>Export selected ZIP</button>
            <FileField inputRef={zipFile} accept=".zip" label="Choose ZIP" />
            <button className="secondary" onClick={() => upload("/api/upload", zipFile.current?.files?.[0], "map")}>Import ZIP</button>
          </div>
        </div>
        <div className="tool-card">
          <h3>Manual VPK</h3>
          <p>Imports one local VPK when a package has already been downloaded elsewhere.</p>
          <div className="actions">
            <FileField inputRef={vpkFile} accept=".vpk" label="Choose VPK" />
            <select value={vpkKind} onChange={(event) => setVpkKind(event.target.value)}>
              <option value="map">Map package</option>
              <option value="mod">Mod</option>
            </select>
            <button onClick={() => upload("/api/upload", vpkFile.current?.files?.[0], vpkKind)}>Import VPK</button>
          </div>
        </div>
      </div>
    </section>
  );
}

function ModsPanel({ addons, selectedManifest, setSelectedManifest, runAction }: {
  addons: Addon[];
  selectedManifest: Set<string>;
  setSelectedManifest: (value: Set<string>) => void;
  runAction: (action: () => Promise<string | undefined>, loading: string) => Promise<void>;
}) {
  const mods = addons.filter((addon) => addon.kind !== "map");
  async function addonState(addon: Addon) {
    const target = addon.state === "enabled" ? "disabled" : "enabled";
    const { payload } = await postForm("/api/addon/state", { filename: addon.filename, state: target });
    return payload.message;
  }
  async function installManifest(addon: Addon) {
    const { payload } = await postForm("/api/manifest/install", { filename: addon.filename });
    return payload.message;
  }
  async function removeManifest(addon: Addon) {
    if (!window.confirm(`Remove source record for ${addon.filename}?`)) return "Remove cancelled";
    const { payload } = await postForm("/api/manifest/remove-record", { filename: addon.filename });
    return payload.message;
  }
  function toggle(addon: Addon, checked: boolean) {
    const next = new Set(selectedManifest);
    if (checked) next.add(addon.filename);
    else next.delete(addon.filename);
    setSelectedManifest(next);
  }
  return (
    <section className="panel">
      <PanelHead title="Mod Management" subtitle="Enable or disable non-map VPK packages; remote records can be reinstalled." badge={`${mods.length} vpks`} />
      <div className="compact-list">
        {!mods.length && <div className="empty-state">No manageable non-map VPK packages yet.</div>}
        {mods.map((addon) => (
          <div className="compact-row" key={addon.filename}>
            <label><input type="checkbox" checked={selectedManifest.has(addon.filename)} onChange={(event) => toggle(addon, event.target.checked)} /> {addon.filename}</label>
            <Pill label={addon.state} tone={statusClass(addon.state)} />
            <span>{addon.state === "remote" ? "not downloaded" : fileSizeMb(addon.size)}</span>
            <div className="actions right">
              {addon.url && <a href={addon.url} target="_blank" rel="noreferrer">Open</a>}
              {addon.state === "remote" && addon.reinstallable && <button onClick={() => runAction(() => installManifest(addon), "Queueing source install...")}>Install Source</button>}
              {addon.state === "remote" && <button className="secondary" onClick={() => runAction(() => removeManifest(addon), "Removing source record...")}>Remove Record</button>}
              {addon.state !== "remote" && <button onClick={() => runAction(() => addonState(addon), "Updating mod state...")}>{addon.state === "enabled" ? "Disable" : "Enable"}</button>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function PluginsPanel({ plugins, runAction }: { plugins: ServerPlugins; runAction: (action: () => Promise<string | undefined>, loading: string) => Promise<void> }) {
  const list = plugins.plugins || [];
  const installed = list.filter((plugin) => plugin.state !== "missing").length;
  async function installStack() {
    if (!window.confirm("Install the conservative plugin stack? This may restart both rooms.")) return "Install cancelled";
    const { payload } = await postForm("/api/server-plugins/install", { stack: "basic" });
    return payload.message;
  }
  async function setPlugin(plugin: ServerPlugin) {
    const target = plugin.state === "enabled" ? "disabled" : "enabled";
    const { payload } = await postForm("/api/server-plugins/state", { plugin: plugin.id, state: target });
    return payload.message;
  }
  async function restart(target: string) {
    if (!window.confirm("Restarting rooms disconnects current players. Continue?")) return "Restart cancelled";
    const { payload } = await postForm("/api/server-plugins/restart", { target });
    return payload.message;
  }
  return (
    <section className="panel">
      <PanelHead title="Server Plugins" subtitle="Manage MetaMod, SourceMod, and the conservative plugin stack." badge={`${installed}/${list.length} plugins`} />
      <div className="health-row">
        <Pill label={`MetaMod ${plugins.metamod ? "installed" : "missing"}`} tone={plugins.metamod ? "ok" : "warn"} />
        <Pill label={`SourceMod ${plugins.sourcemod ? "installed" : "missing"}`} tone={plugins.sourcemod ? "ok" : "warn"} />
      </div>
      <div className="actions">
        <button onClick={() => runAction(installStack, "Queueing plugin install...")}>Install Stack</button>
        <button className="danger" onClick={() => runAction(() => restart("all"), "Restarting rooms...")}>Restart Both</button>
        <button className="secondary" onClick={() => runAction(() => restart("room1"), "Restarting Room 1...")}>Restart Room 1</button>
        <button className="secondary" onClick={() => runAction(() => restart("room2"), "Restarting Room 2...")}>Restart Room 2</button>
      </div>
      <div className="compact-list">
        {list.map((plugin) => (
          <div className="compact-row" key={plugin.id}>
            <div>
              <strong>{plugin.label}</strong>
              <div className="muted mono">{plugin.filename || ""}</div>
            </div>
            <Pill label={plugin.state} tone={statusClass(plugin.state)} />
            <span>{plugin.size ? formatBytes(plugin.size) : ""}</span>
            <div className="actions right">
              {plugin.state !== "missing" && <button onClick={() => runAction(() => setPlugin(plugin), "Updating server plugin...")}>{plugin.state === "enabled" ? "Disable" : "Enable"}</button>}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function CampaignPanel({ campaigns, mapCount }: { campaigns: Campaign[]; mapCount: number }) {
  const [query, setQuery] = useState("");
  const term = query.trim().toLowerCase();
  const filtered = term
    ? campaigns
        .map((campaign) => ({
          ...campaign,
          maps: campaign.maps.filter((map) =>
            `${map.display_name} ${map.name}`.toLowerCase().includes(term) || campaign.title.toLowerCase().includes(term)
          )
        }))
        .filter((campaign) => campaign.maps.length)
    : campaigns;
  return (
    <section className="panel">
      <PanelHead title="Installed Maps" subtitle="Campaigns are grouped by detected mission metadata; Other contains unrecognized maps." badge={`${mapCount} maps`} />
      <div className="filter-row">
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter campaign or map name" />
      </div>
      <div className="campaign-list">
        {!filtered.length && <div className="empty-state">No maps match this filter.</div>}
        {filtered.map((campaign) => (
          <details key={campaign.id} open={term ? true : campaign.source !== "other"}>
            <summary>{campaign.title} <span>{campaign.maps.length} maps</span></summary>
            <div className="chapter-grid">
              {campaign.maps.map((map) => (
                <div key={map.name}><span>{map.chapter}.</span> {map.display_name} <code>{map.name}</code></div>
              ))}
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}

function PanelHead({ title, subtitle, badge }: { title: string; subtitle?: string; badge?: string }) {
  return (
    <div className="panel-head">
      <div>
        <h2>{title}</h2>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {badge && <Pill label={badge} />}
    </div>
  );
}

function Pill({ label, tone = "" }: { label: string; tone?: string }) {
  return <span className={`pill ${tone}`}>{label}</span>;
}

function Segmented({ value, setValue, options }: { value: string; setValue: (value: string) => void; options: Array<[string, string]> }) {
  return (
    <div className="segmented">
      {options.map(([key, label]) => (
        <button key={key} className={value === key ? "active" : ""} onClick={() => setValue(key)}>{label}</button>
      ))}
    </div>
  );
}

function RowMenu({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    function onClick(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);
  return (
    <div className="row-menu" ref={ref}>
      <button className="secondary menu-trigger" aria-label="More actions" onClick={() => setOpen((value) => !value)}>⋯</button>
      {open && <div className="menu-popover" onClick={() => setOpen(false)}>{children}</div>}
    </div>
  );
}

function FileField({ inputRef, accept, label = "Choose file", onChange, multiple, onChangeFiles }: { inputRef: RefObject<HTMLInputElement>; accept?: string; label?: string; onChange?: (size: number) => void; multiple?: boolean; onChangeFiles?: (files: File[]) => void }) {
  const [name, setName] = useState("");
  return (
    <label className="file-field">
      <span className="file-button">{label}</span>
      <span className="file-name">{name || "No file selected"}</span>
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        onChange={(event) => {
          const files = Array.from(event.target.files || []);
          setName(files.length > 1 ? `${files.length} files selected` : files[0]?.name || "");
          onChange?.(files[0]?.size || 0);
          onChangeFiles?.(files);
        }}
      />
    </label>
  );
}

function downloadBlob(response: Response, fallback: string) {
  response.blob().then((blob) => {
    const disposition = response.headers.get("Content-Disposition") || "";
    const match = disposition.match(/filename="([^"]+)"/);
    const filename = match ? match[1] : fallback;
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  });
}
