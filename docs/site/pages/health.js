import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, NextSteps } from '../components/Docs';

const toc = [
  { id: 'overview',   label: 'Overview' },
  { id: 'platforms',  label: 'Platforms' },
  { id: 'devices',    label: 'Supported Devices' },
  { id: 'metrics',    label: 'Metric Types' },
  { id: 'setup',      label: 'Setup Guide' },
  { id: 'api',        label: 'API Reference' },
  { id: 'webhooks',   label: 'Webhooks (Apple / Samsung)' },
  { id: 'chat',       label: 'Asking Luna About Your Health' },
];

const Badge = ({ label, color = 'purple' }) => (
  <span className={`int-badge int-badge-${color}`}>{label}</span>
);

const Card = ({ icon, title, subtitle, badges = [], note }) => (
  <div className="int-card">
    <div className="int-icon">{icon}</div>
    <div className="int-card-body">
      <div className="int-card-head">
        <span className="int-title">{title}</span>
        {badges.map(b => <Badge key={b.label} label={b.label} color={b.color} />)}
      </div>
      {subtitle && <p className="int-subtitle">{subtitle}</p>}
      {note    && <p className="int-note">{note}</p>}
    </div>
  </div>
);

const MetricRow = ({ type, unit, platforms, description }) => (
  <tr>
    <td><code>{type}</code></td>
    <td>{unit}</td>
    <td style={{ fontSize: 12, color: '#6b7280' }}>{platforms}</td>
    <td style={{ fontSize: 12, color: '#9ca3af' }}>{description}</td>
  </tr>
);

const DeviceCard = ({ icon, platform, color, devices, authType, metrics }) => (
  <div style={{
    background: '#0a0d18',
    border: `1px solid ${color}33`,
    borderRadius: 10,
    padding: '16px 18px',
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <span style={{ fontSize: 20 }}>{icon}</span>
      <span style={{ fontWeight: 700, fontSize: 14, color }}>{platform}</span>
      <span style={{
        marginLeft: 'auto',
        fontSize: 9,
        fontWeight: 600,
        padding: '2px 7px',
        borderRadius: 4,
        background: `${color}18`,
        color,
        border: `1px solid ${color}33`,
      }}>{authType}</span>
    </div>
    <div style={{ fontSize: 12, color: '#9ca3af', lineHeight: 1.7 }}>
      {devices.map(d => <div key={d}>• {d}</div>)}
    </div>
    <div style={{
      marginTop: 4,
      fontSize: 11,
      color: '#6b7280',
      borderTop: `1px solid #ffffff08`,
      paddingTop: 8,
    }}>{metrics}</div>
  </div>
);

export default function Health() {
  return (
    <DocsLayout
      title="Health Integrations"
      description="Connect Fitbit, Google Fit, Oura Ring, Withings, Garmin, Apple Health, and Samsung Health to give Luna awareness of your health metrics, sleep, and fitness data."
      toc={toc}
    >

      {/* Overview */}
      <section id="overview">
        <img
          src="/images/health-platforms.svg"
          alt="Health platform integrations — Fitbit, Google Fit, Oura, Withings, Garmin, Apple Health, Samsung Health flowing into Luna"
          style={{ width: '100%', borderRadius: 12, marginBottom: 24, border: '1px solid #1e1b4b' }}
        />

        <p>
          Luna can pull health and fitness data from 7 major platforms and 16 metric types.
          All data is stored locally in SQLite — nothing is sent to any cloud. You query it
          through chat or the REST API.
        </p>
        <p style={{ marginTop: 12 }}>
          Platforms with a REST API (Fitbit, Google Fit, Oura, Withings, Garmin) sync on demand
          or on a schedule. Apple Health and Samsung Health — which have no public REST API —
          use a webhook receiver: a companion iOS or Android app pushes data to Luna.
        </p>

        <Callout type="info" title="All opt-in, all local">
          <p>
            No health credentials are required to run Luna. Every platform is independently
            opt-in. Data is stored in your local <code>luna.db</code> SQLite database and
            never leaves your machine.
          </p>
        </Callout>
      </section>

      {/* Platforms */}
      <section id="platforms">
        <h2>Platforms</h2>

        <Card
          icon="⌚"
          title="Fitbit"
          subtitle="The most comprehensive health API. Covers steps, distance, calories, heart rate, HRV, all sleep stages, SpO2, breathing rate, skin temperature, and weight. Uses OAuth2 — create a free app at app.fitbit.com."
          badges={[{ label: 'OAuth2', color: 'blue' }, { label: 'Full coverage', color: 'green' }]}
          note="fitbit_client_id= · fitbit_client_secret= · then: GET /api/health/oauth/authorize/fitbit"
        />
        <Card
          icon="🏃"
          title="Google Fit"
          subtitle="Google's fitness aggregation platform. Supports activity (steps, distance, calories), heart rate, weight, body fat, SpO2, and sleep sessions from any Android wearable synced to Google Fit. Uses Google OAuth2 — create credentials in Google Cloud Console."
          badges={[{ label: 'OAuth2', color: 'blue' }]}
          note="google_fit_client_id= · google_fit_client_secret= · then: GET /api/health/oauth/authorize/google_fit"
        />
        <Card
          icon="💍"
          title="Oura Ring"
          subtitle="Oura's v2 API gives richly detailed sleep stages, HRV, resting heart rate, respiratory rate, readiness scores, stress levels, and daily activity. Auth is a simple personal access token — no OAuth flow needed."
          badges={[{ label: 'API key', color: 'purple' }, { label: 'Best sleep data', color: 'green' }]}
          note="oura_api_key=  — get it at cloud.ouraring.com/user/api-tokens"
        />
        <Card
          icon="⚖️"
          title="Withings"
          subtitle="Specialises in medical-grade smart scales (weight, BMI, body fat), blood pressure monitors, and sleep mats. The best source for blood pressure and body composition data. Uses OAuth2."
          badges={[{ label: 'OAuth2', color: 'blue' }, { label: 'Blood pressure', color: 'purple' }]}
          note="withings_client_id= · withings_client_secret= · then: GET /api/health/oauth/authorize/withings"
        />
        <Card
          icon="🏔"
          title="Garmin Connect"
          subtitle="Detailed GPS workout data, Body Battery (readiness), stress tracking, VO2 Max, sleep stages, and SpO2. Uses the garth library to authenticate with Garmin Connect — requires your Garmin account credentials."
          badges={[{ label: 'Credentials', color: 'gray' }, { label: 'pip install garth', color: 'blue' }]}
          note="garmin_email= · garmin_password= — requires: pip install garth"
        />
        <Card
          icon="🍎"
          title="Apple Health"
          subtitle="iPhone and Apple Watch generate the richest per-minute health data of any consumer platform, but Apple provides no public REST API. Luna uses a webhook receiver — the free 'Health Auto Export' iOS app pushes data to Luna on a schedule."
          badges={[{ label: 'Webhook', color: 'gray' }, { label: 'iOS app needed', color: 'blue' }]}
          note="Endpoint: POST /api/health/webhook/apple  ·  See setup section below"
        />
        <Card
          icon="📱"
          title="Samsung Health"
          subtitle="Galaxy Watch and Galaxy Fit data through compatible Android exporter apps. Samsung Health has no public REST API, so Luna uses the same webhook approach as Apple Health — point a compatible exporter at /api/health/webhook/samsung."
          badges={[{ label: 'Webhook', color: 'gray' }, { label: 'Android app needed', color: 'blue' }]}
          note="Endpoint: POST /api/health/webhook/samsung  ·  See setup section below"
        />
      </section>

      {/* Supported Devices */}
      <section id="devices">
        <h2>Supported Devices</h2>
        <p>Every device that syncs to one of the 7 integrated platforms is supported.</p>

        <img
          src="/images/health-devices.svg"
          alt="Supported smartwatches and wearables"
          style={{ width: '100%', borderRadius: 12, margin: '20px 0', border: '1px solid #1e1b4b' }}
        />

        <div style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))',
          gap: 12,
          marginTop: 8,
        }}>
          <DeviceCard
            icon="⌚"
            platform="Fitbit"
            color="#00b0b9"
            authType="OAuth2 API"
            devices={[
              'Charge 5 / 6',
              'Inspire 3',
              'Versa 3 / 4',
              'Sense 2',
              'Luxe',
              'Ace 3',
              'Aria 2 (smart scale)',
            ]}
            metrics="Steps · HR · HRV · Sleep stages · SpO2 · Skin temp · Calories · Breathing · Weight"
          />
          <DeviceCard
            icon="🏔"
            platform="Garmin"
            color="#cf0a2c"
            authType="garth library"
            devices={[
              'Forerunner 255 / 265 / 965',
              'Fenix 7 / 7S / 7X / 8',
              'Venu 3 / 3S',
              'Vivoactive 5',
              'Vivosmart 5',
              'Instinct 2',
              'All Garmin Connect devices',
            ]}
            metrics="Steps · HR · HRV · Sleep · VO2 Max · Body Battery · Stress · SpO2 · Calories"
          />
          <DeviceCard
            icon="💍"
            platform="Oura Ring"
            color="#d4a017"
            authType="Personal Token"
            devices={[
              'Oura Ring Gen 3',
              'Oura Ring 4',
              'Form factor: finger ring',
            ]}
            metrics="Sleep stages · HRV · Resting HR · Readiness · Stress · Respiratory rate · Steps · SpO2"
          />
          <DeviceCard
            icon="⚖️"
            platform="Withings"
            color="#00c851"
            authType="OAuth2 API"
            devices={[
              'ScanWatch 2',
              'Steel HR Sport',
              'Move ECG',
              'Body+ (smart scale)',
              'BPM Core (blood pressure)',
              'Thermo (thermometer)',
            ]}
            metrics="Weight · BMI · Body fat · Blood pressure · HR · Sleep · ECG"
          />
          <DeviceCard
            icon="🍎"
            platform="Apple Watch"
            color="#aeaeb2"
            authType="Webhook"
            devices={[
              'Apple Watch Series 4 through 10',
              'Apple Watch Ultra 1 & 2',
              'Apple Watch SE (all gen)',
            ]}
            metrics="All HealthKit metrics via Health Auto Export iOS app — full coverage of every sensor"
          />
          <DeviceCard
            icon="📱"
            platform="Samsung Galaxy Watch"
            color="#748ffc"
            authType="Webhook"
            devices={[
              'Galaxy Watch 4 / 5 / 6 / 7',
              'Galaxy Watch Ultra',
              'Galaxy Fit 3',
            ]}
            metrics="Steps · HR · Sleep · Calories · SpO2 · Stress · VO2 Max — via compatible Android exporter"
          />
        </div>

        <Callout type="note" title="Google Fit ecosystem">
          <p>
            Google Fit aggregates data from many Android wearables — Pixel Watch 1/2/3,
            Sony Smartwatch, TicWatch, and any wearable running Wear OS. If your device
            syncs to Google Fit, set <code>google_fit_client_id</code> and it works automatically.
          </p>
        </Callout>
      </section>

      {/* Metric Types */}
      <section id="metrics">
        <h2>Metric Types</h2>

        <img
          src="/images/health-metrics.svg"
          alt="Health metrics dashboard — showing all 16 metric types with live values"
          style={{ width: '100%', borderRadius: 12, margin: '8px 0 20px', border: '1px solid #1e1b4b' }}
        />

        <table>
          <thead>
            <tr>
              <th>metric_type</th>
              <th>Unit</th>
              <th>Platforms</th>
              <th>Description</th>
            </tr>
          </thead>
          <tbody>
            <MetricRow type="steps"                  unit="steps"       platforms="Fitbit, Google Fit, Oura, Garmin, Apple, Samsung" description="Total step count for the day" />
            <MetricRow type="distance_km"            unit="km"          platforms="Fitbit, Google Fit, Oura, Garmin, Apple, Samsung" description="Total distance walked / run" />
            <MetricRow type="calories"               unit="kcal"        platforms="Fitbit, Google Fit, Oura, Garmin, Apple, Samsung" description="Active calorie burn" />
            <MetricRow type="heart_rate"             unit="bpm"         platforms="All (intra-day avg)"   description="Average heart rate" />
            <MetricRow type="resting_heart_rate"     unit="bpm"         platforms="Fitbit, Oura, Garmin"  description="Daily resting heart rate" />
            <MetricRow type="hrv"                    unit="ms"          platforms="Fitbit, Oura, Garmin"  description="Heart rate variability (RMSSD / SDNN)" />
            <MetricRow type="sleep_duration_min"     unit="min"         platforms="All"                   description="Total sleep duration" />
            <MetricRow type="sleep_deep_min"         unit="min"         platforms="Fitbit, Oura, Garmin"  description="Deep (N3) sleep minutes" />
            <MetricRow type="sleep_rem_min"          unit="min"         platforms="Fitbit, Oura, Garmin"  description="REM sleep minutes" />
            <MetricRow type="sleep_light_min"        unit="min"         platforms="Fitbit, Oura, Garmin"  description="Light (N1+N2) sleep minutes" />
            <MetricRow type="sleep_score"            unit="score"       platforms="Oura, Withings"         description="Overall sleep quality score" />
            <MetricRow type="blood_oxygen_pct"       unit="%"           platforms="Fitbit, Oura, Garmin, Apple" description="SpO2 / blood oxygen saturation" />
            <MetricRow type="weight_kg"              unit="kg"          platforms="Fitbit, Withings"       description="Body weight" />
            <MetricRow type="bmi"                    unit="kg/m²"       platforms="Fitbit, Withings"       description="Body mass index" />
            <MetricRow type="body_fat_pct"           unit="%"           platforms="Google Fit, Withings"   description="Body fat percentage" />
            <MetricRow type="blood_pressure_systolic"  unit="mmHg"      platforms="Withings"               description="Systolic blood pressure" />
            <MetricRow type="blood_pressure_diastolic" unit="mmHg"      platforms="Withings"               description="Diastolic blood pressure" />
            <MetricRow type="stress_score"           unit="score"       platforms="Oura, Garmin"           description="Stress level score" />
            <MetricRow type="readiness_score"        unit="score"       platforms="Oura, Garmin"           description="Daily readiness / recovery" />
            <MetricRow type="vo2_max"                unit="mL/kg/min"   platforms="Garmin, Apple"          description="Cardiorespiratory fitness estimate" />
            <MetricRow type="respiratory_rate"       unit="rpm"         platforms="Fitbit, Oura"           description="Breathing rate" />
            <MetricRow type="skin_temp_c"            unit="°C"          platforms="Fitbit"                 description="Skin temperature (nightly relative)" />
            <MetricRow type="active_minutes"         unit="min"         platforms="All"                    description="Vigorous + moderate active minutes" />
          </tbody>
        </table>
      </section>

      {/* Setup Guide */}
      <section id="setup">
        <h2>Setup Guide</h2>

        <h3>Fitbit</h3>
        <ol style={{ paddingLeft: 20, lineHeight: 2.2 }}>
          <li>Go to <strong>app.fitbit.com/oauth2/applications</strong> and create a new app</li>
          <li>Set <em>OAuth 2.0 Application Type</em> to <strong>Personal</strong></li>
          <li>Set <em>Redirect URL</em> to <code>http://localhost:8899/api/health/oauth/callback</code></li>
          <li>Copy the <strong>Client ID</strong> and <strong>Client Secret</strong> to <code>.env</code></li>
          <li>Open: <code>http://localhost:8899/api/health/oauth/authorize/fitbit</code></li>
          <li>Authorise → copy the returned tokens to <code>.env</code></li>
        </ol>
        <CodeFile label=".env">
          <pre><code>{`fitbit_client_id=23ABC4
fitbit_client_secret=abc123...
fitbit_access_token=eyJ...   # returned by the OAuth callback
fitbit_refresh_token=abc...  # returned by the OAuth callback`}</code></pre>
        </CodeFile>

        <h3>Google Fit</h3>
        <ol style={{ paddingLeft: 20, lineHeight: 2.2 }}>
          <li>Open <strong>Google Cloud Console</strong> → APIs &amp; Services → Enable <em>Fitness API</em></li>
          <li>Credentials → Create OAuth client ID → Application type: <strong>Web application</strong></li>
          <li>Add redirect URI: <code>http://localhost:8899/api/health/oauth/callback</code></li>
          <li>Add credentials to <code>.env</code>, then visit the authorize URL</li>
        </ol>
        <CodeFile label=".env">
          <pre><code>{`google_fit_client_id=123456...apps.googleusercontent.com
google_fit_client_secret=GOCSPX-...
google_fit_access_token=ya29...    # returned by callback
google_fit_refresh_token=1//...    # returned by callback`}</code></pre>
        </CodeFile>

        <h3>Oura Ring</h3>
        <ol style={{ paddingLeft: 20, lineHeight: 2.2 }}>
          <li>Log in at <strong>cloud.ouraring.com</strong> → User Settings → Personal Access Tokens</li>
          <li>Create a token and paste it into <code>.env</code></li>
        </ol>
        <CodeFile label=".env">
          <pre><code>{`oura_api_key=YOUR_PERSONAL_TOKEN`}</code></pre>
        </CodeFile>

        <h3>Withings</h3>
        <ol style={{ paddingLeft: 20, lineHeight: 2.2 }}>
          <li>Go to <strong>developer.withings.com</strong> → Create an app</li>
          <li>Set redirect URI to <code>http://localhost:8899/api/health/oauth/callback</code></li>
          <li>Add credentials to <code>.env</code>, then visit the authorize URL</li>
        </ol>
        <CodeFile label=".env">
          <pre><code>{`withings_client_id=abc123
withings_client_secret=def456
withings_access_token=...   # returned by callback
withings_refresh_token=...  # returned by callback`}</code></pre>
        </CodeFile>

        <h3>Garmin</h3>
        <ol style={{ paddingLeft: 20, lineHeight: 2.2 }}>
          <li>Install the garth library: <code>pip install garth</code></li>
          <li>Add your Garmin account email and password to <code>.env</code></li>
        </ol>
        <CodeFile label=".env">
          <pre><code>{`garmin_email=you@email.com
garmin_password=your-garmin-password`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="Trigger a sync from chat">
          <p>Once configured, ask Luna to sync: <em>"sync my health data from Fitbit"</em> or
          use the API directly: <code>POST /api/health/sync?platform=fitbit</code></p>
        </Callout>
      </section>

      {/* Webhooks */}
      <section id="webhooks">
        <h2>Webhooks — Apple Health &amp; Samsung Health</h2>
        <p>
          Apple HealthKit and Samsung Health are closed ecosystems with no public REST API.
          Luna receives data via HTTP push from a companion app running on your phone.
        </p>

        <h3>Apple Health — Health Auto Export (iOS, free)</h3>
        <ol style={{ paddingLeft: 20, lineHeight: 2.2 }}>
          <li>Install <strong>Health Auto Export</strong> from the App Store (free tier is sufficient)</li>
          <li>Open the app → <em>Automations</em> → Add → <em>REST API</em></li>
          <li>Set <em>URL</em> to <code>https://YOUR_HOST/api/health/webhook/apple</code></li>
          <li>Add header: <code>X-Health-Secret: &lt;your health_webhook_secret&gt;</code></li>
          <li>Choose metrics to export and set an export interval (e.g. hourly)</li>
          <li>Set <code>health_webhook_secret</code> in Luna's <code>.env</code> to the same value</li>
        </ol>

        <CodeFile label=".env">
          <pre><code>{`health_webhook_secret=some-long-random-string`}</code></pre>
        </CodeFile>

        <Callout type="note" title="Local network access">
          <p>
            Your iPhone needs to reach Luna's server. On a home network, set{' '}
            <code>host=0.0.0.0</code> in <code>.env</code> and use your machine's LAN IP
            (e.g. <code>http://192.168.1.10:8899/api/health/webhook/apple</code>).
            For remote access, use <code>luna tunnel</code> or expose via a reverse proxy.
          </p>
        </Callout>

        <h3>Samsung Health</h3>
        <ol style={{ paddingLeft: 20, lineHeight: 2.2 }}>
          <li>Install a compatible Android health exporter app (e.g. <em>Health Export for Samsung</em>)</li>
          <li>Configure it to POST to <code>https://YOUR_HOST/api/health/webhook/samsung</code></li>
          <li>Add header: <code>X-Health-Secret: &lt;your health_webhook_secret&gt;</code></li>
          <li>Alternatively, if your app supports Health Auto Export format, it works with the Samsung endpoint too</li>
        </ol>

        <h3>Webhook payload format</h3>
        <p>Both endpoints accept the <strong>Health Auto Export</strong> JSON format natively:</p>
        <CodeFile label="example payload">
          <pre><code>{`{
  "data": {
    "metrics": [
      {
        "name": "heart_rate",
        "units": "bpm",
        "data": [
          { "date": "2026-05-21T08:32:00+00:00", "qty": 68 },
          { "date": "2026-05-21T09:15:00+00:00", "qty": 72 }
        ]
      },
      {
        "name": "step_count",
        "units": "count",
        "data": [
          { "date": "2026-05-21", "qty": 8432 }
        ]
      }
    ]
  }
}`}</code></pre>
        </CodeFile>
      </section>

      {/* API Reference */}
      <section id="api">
        <h2>API Reference</h2>

        <table>
          <thead>
            <tr><th>Endpoint</th><th>Method</th><th>Description</th></tr>
          </thead>
          <tbody>
            <tr><td><code>/api/health/status</code></td><td>GET</td><td>All platform statuses and last sync timestamps</td></tr>
            <tr><td><code>/api/health/metrics</code></td><td>GET</td><td>Query stored metrics — filter by platform, type, date range</td></tr>
            <tr><td><code>/api/health/summary</code></td><td>GET</td><td>Daily cross-platform summary (defaults to today)</td></tr>
            <tr><td><code>/api/health/sync</code></td><td>POST</td><td>Trigger sync — <code>?platform=fitbit</code> or omit for all</td></tr>
            <tr><td><code>/api/health/oauth/authorize/{`{platform}`}</code></td><td>GET</td><td>Start OAuth2 flow (fitbit / google_fit / withings)</td></tr>
            <tr><td><code>/api/health/oauth/callback</code></td><td>GET</td><td>Completes OAuth2, returns tokens to add to .env</td></tr>
            <tr><td><code>/api/health/webhook/apple</code></td><td>POST</td><td>Apple Health inbound push (Health Auto Export format)</td></tr>
            <tr><td><code>/api/health/webhook/samsung</code></td><td>POST</td><td>Samsung Health inbound push</td></tr>
            <tr><td><code>/api/health/metric-types</code></td><td>GET</td><td>List all supported metric type names and units</td></tr>
          </tbody>
        </table>

        <h3>Query examples</h3>
        <CodeFile label="terminal">
          <pre><code>{`# All platform statuses
curl http://localhost:8899/api/health/status

# Today's cross-platform summary
curl http://localhost:8899/api/health/summary

# Last 30 days of heart rate from Fitbit
curl "http://localhost:8899/api/health/metrics?platform=fitbit&metric_type=heart_rate&from=2026-04-21&to=2026-05-21"

# Trigger sync for all configured platforms
curl -X POST http://localhost:8899/api/health/sync

# Sync only Oura
curl -X POST "http://localhost:8899/api/health/sync?platform=oura"

# Sync yesterday's data
curl -X POST "http://localhost:8899/api/health/sync?platform=fitbit&date=2026-05-20"

# Start Fitbit OAuth (open in browser)
open http://localhost:8899/api/health/oauth/authorize/fitbit`}</code></pre>
        </CodeFile>

        <CodeFile label="example response — /api/health/summary">
          <pre><code>{`{
  "date": "2026-05-21",
  "metrics": {
    "steps":             [{ "platform": "fitbit", "value": 8432,  "unit": "steps" }],
    "heart_rate":        [{ "platform": "fitbit", "value": 72,    "unit": "bpm" },
                          { "platform": "oura",   "value": 69,    "unit": "bpm" }],
    "hrv":               [{ "platform": "oura",   "value": 48,    "unit": "ms" }],
    "sleep_duration_min":[{ "platform": "fitbit", "value": 444,   "unit": "min" }],
    "sleep_deep_min":    [{ "platform": "fitbit", "value": 82,    "unit": "min" }],
    "readiness_score":   [{ "platform": "oura",   "value": 82,    "unit": "score" }],
    "weight_kg":         [{ "platform": "withings","value": 74.2, "unit": "kg" }]
  }
}`}</code></pre>
        </CodeFile>
      </section>

      {/* Chat */}
      <section id="chat">
        <h2>Asking Luna About Your Health</h2>
        <p>
          Once synced, health data is available to the LLM as context. Luna can answer
          questions, spot trends, and give personalised suggestions based on your actual data.
        </p>

        <CodeFile label="chat examples">
          <pre><code>{`"How was my sleep last night?"
→ You slept 7h 24m with 82 min deep and 1h 48m REM. HRV was 48ms — solid recovery.

"How many steps did I take this week?"
→ Your 7-day average is 9,241 steps. Best day was Thursday at 12,800.

"Is my heart rate normal?"
→ Resting HR today is 62bpm, down from your 30-day average of 68. That's a positive trend.

"How's my readiness today?"
→ Oura scores your readiness at 82/100. Your HRV is above your average and sleep debt is low.

"Sync my Fitbit and tell me how my recovery looks"
→ (syncs Fitbit, then answers based on fresh data)

"Show me my blood pressure readings from the past week"
→ (queries Withings data, summarizes the trend)

"How does my sleep compare to last month?"
→ (queries last 30 days, computes averages, compares)

"I went for a run today — did my heart rate zones look right?"
→ (reads Garmin workout data if synced)`}</code></pre>
        </CodeFile>

        <Callout type="tip" title="Keep data fresh">
          <p>
            Set up a daily cron or scheduler to auto-sync.
            POST <code>/api/health/sync</code> from a task scheduler
            (Windows Task Scheduler, cron, or Luna's built-in scheduler) each morning
            to have overnight sleep and yesterday's activity ready when you wake up.
          </p>
        </Callout>
      </section>

      <NextSteps items={[
        { href: '/integrations', label: 'Integrations', title: 'All Integrations', desc: 'See every platform Luna connects to — workspace, channels, live data, and more.' },
        { href: '/agent',       label: 'Agent',        title: 'Agent & Skills',   desc: 'Build custom health automations using Luna\'s planner and tool system.' },
        { href: '/memory',      label: 'Memory',       title: 'Memory',           desc: 'How Luna stores and recalls health facts from conversation.' },
      ]} />
    </DocsLayout>
  );
}
