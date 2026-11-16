import { useEffect, useState } from 'react'
import { api } from '../../api/client'
import { ShieldCheck, Puzzle, Folder, ClipboardList, History, RefreshCw, Plus } from 'lucide-react'

type AgentData = {
  skills: any[]
  audit: any[]
  permissions: Record<string, any>
  workspace: any[]
  tasks: any[]
  browser: any
}

export function AgentView() {
  const [data, setData] = useState<AgentData>({
    skills: [],
    audit: [],
    permissions: {},
    workspace: [],
    tasks: [],
    browser: null,
  })
  const [taskText, setTaskText] = useState('')
  const [loading, setLoading] = useState(false)

  const load = async () => {
    setLoading(true)
    try {
      const [skills, audit, perms, workspace, tasks, browser] = await Promise.all([
        api.getAgentSkills(),
        api.getAgentAudit(80),
        api.getAgentPermissions(),
        api.getWorkspace(),
        api.getAgentTasks(),
        api.getBrowserStatus(),
      ])
      setData({ skills, audit, permissions: perms.tools ?? {}, workspace, tasks, browser })
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load().catch(() => {})
  }, [])

  const createTask = async () => {
    const text = taskText.trim()
    if (!text) return
    await api.createAgentTask(text)
    setTaskText('')
    await load()
  }

  return (
    <div className="h-full overflow-y-auto bg-luna-bg text-luna-text">
      <div className="max-w-6xl mx-auto p-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-xl font-semibold">Agent Control</h2>
            <p className="text-sm text-luna-dim mt-1">Skills, permissions, workspace, browser layer, tasks, and audit log.</p>
          </div>
          <button
            onClick={() => load()}
            className="inline-flex items-center gap-2 rounded-md border border-luna-border px-3 py-2 text-sm text-luna-muted hover:text-luna-text hover:bg-luna-card"
          >
            <RefreshCw size={15} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        <section className="grid grid-cols-1 xl:grid-cols-3 gap-4">
          <Panel title="Skills" icon={Puzzle}>
            <div className="space-y-2">
              {data.skills.map((skill) => (
                <div key={skill.id} className="rounded-md border border-luna-border bg-luna-surface p-3">
                  <div className="text-sm font-medium">{skill.name}</div>
                  <div className="text-xs text-luna-dim mt-1">{skill.description}</div>
                  <div className="text-[11px] text-luna-muted mt-2">permissions: {(skill.permissions ?? []).join(', ') || 'none'}</div>
                </div>
              ))}
              {!data.skills.length && <Empty text="No skills installed." />}
            </div>
          </Panel>

          <Panel title="Workspace" icon={Folder}>
            <div className="space-y-2">
              {data.workspace.map((item) => (
                <div key={item.path} className="flex items-center justify-between rounded-md border border-luna-border bg-luna-surface px-3 py-2">
                  <span className="text-sm truncate">{item.path}</span>
                  <span className="text-[11px] text-luna-dim">{item.type}</span>
                </div>
              ))}
              {!data.workspace.length && <Empty text="Workspace is empty." />}
            </div>
          </Panel>

          <Panel title="Browser Layer" icon={ShieldCheck}>
            <div className="rounded-md border border-luna-border bg-luna-surface p-3">
              <div className="text-sm">{data.browser?.available ? 'Playwright available' : 'HTTP reader active'}</div>
              <div className="text-xs text-luna-dim mt-1">
                {data.browser?.available ? 'Full browser automation can be enabled.' : data.browser?.install ?? 'Browser status unknown.'}
              </div>
            </div>
          </Panel>
        </section>

        <section className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          <Panel title="Agent Tasks" icon={ClipboardList}>
            <div className="flex gap-2 mb-3">
              <input
                value={taskText}
                onChange={(e) => setTaskText(e.target.value)}
                placeholder="Research, plan, or execute a multi-step task"
                className="flex-1 rounded-md border border-luna-border bg-luna-surface px-3 py-2 text-sm outline-none focus:border-luna-primary"
              />
              <button onClick={createTask} className="rounded-md bg-luna-primary px-3 py-2 text-sm text-white inline-flex items-center gap-2">
                <Plus size={14} />
                Add
              </button>
            </div>
            <div className="space-y-2">
              {data.tasks.map((task) => (
                <div key={task.id} className="rounded-md border border-luna-border bg-luna-surface p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium truncate">{task.description}</div>
                    <span className="text-[11px] text-luna-dim">{task.status}</span>
                  </div>
                  {(task.steps ?? []).slice(0, 4).map((step: string, i: number) => (
                    <div key={i} className="text-xs text-luna-muted mt-1">{i + 1}. {step}</div>
                  ))}
                </div>
              ))}
              {!data.tasks.length && <Empty text="No agent tasks yet." />}
            </div>
          </Panel>

          <Panel title="Audit Log" icon={History}>
            <div className="space-y-2">
              {data.audit.map((event, index) => (
                <div key={`${event.ts}-${index}`} className="rounded-md border border-luna-border bg-luna-surface p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-medium">{event.action}</div>
                    <span className="text-[11px] text-luna-dim">{event.status}</span>
                  </div>
                  <div className="text-xs text-luna-dim mt-1">{event.tool || event.result || event.ts}</div>
                </div>
              ))}
              {!data.audit.length && <Empty text="No audited actions yet." />}
            </div>
          </Panel>
        </section>

        <Panel title="Permissions" icon={ShieldCheck}>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
            {Object.entries(data.permissions).map(([name, info]: [string, any]) => (
              <div key={name} className="rounded-md border border-luna-border bg-luna-surface p-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium truncate">{name}</div>
                  <span className="text-[11px] uppercase text-luna-dim">{info.mode}</span>
                </div>
                <div className="text-xs text-luna-muted mt-1">{info.description}</div>
              </div>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  )
}

function Panel({ title, icon: Icon, children }: { title: string; icon: any; children: React.ReactNode }) {
  return (
    <section className="rounded-lg border border-luna-border bg-luna-card/40 p-4">
      <div className="flex items-center gap-2 mb-3">
        <Icon size={16} className="text-luna-accent" />
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      {children}
    </section>
  )
}

function Empty({ text }: { text: string }) {
  return <div className="rounded-md border border-dashed border-luna-border p-4 text-sm text-luna-dim">{text}</div>
}
