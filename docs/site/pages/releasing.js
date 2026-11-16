import DocsLayout from '../components/DocsLayout';
import { Callout, CodeFile, Steps, Step } from '../components/Docs';

const toc = [
  { id: 'what',   label: 'What a release publishes' },
  { id: 'steps',  label: 'Cutting a release' },
  { id: 'local',  label: 'Building locally' },
  { id: 'notes',  label: 'Signing notes' },
];

export default function Releasing() {
  return (
    <DocsLayout
      title="Releasing"
      description="One GitHub Release builds the installers and the container image."
      toc={toc}
    >
      <section>
        <h2 id="what">What a release publishes</h2>
        <table>
          <thead><tr><th>What</th><th>Where</th></tr></thead>
          <tbody>
            <tr><td>Windows installer <code>Luna-Setup-&lt;version&gt;.exe</code> (+ zip)</td><td>Attached to the release</td></tr>
            <tr><td>Android app <code>Luna-&lt;version&gt;-android.apk</code></td><td>Attached to the release</td></tr>
            <tr><td>iOS simulator build</td><td>Attached to the release</td></tr>
            <tr><td>Container image</td><td><code>ghcr.io/sehastrajit-s/luna:&lt;version&gt;</code> and <code>:latest</code></td></tr>
          </tbody>
        </table>
        <p>
          Workflows: <code>.github/workflows/build-release.yml</code> (apps) and <code>.github/workflows/docker.yml</code>
          (image; it also smoke-tests the image on every pull request).
        </p>
      </section>

      <section>
        <h2 id="steps">Cutting a release</h2>
        <Steps>
          <Step num="1" title="Bump the version">
            <p>Edit <code>"version"</code> in <code>interfaces/desktop/package.json</code>. It names every file and image tag.</p>
          </Step>
          <Step num="2" title="Merge to main">
            <p>With <code>npm run test:smoke</code>, <code>npm run build</code> and the container check green on the PR.</p>
          </Step>
          <Step num="3" title="Publish the release">
            <CodeFile label="terminal">
              <pre><code>{`gh release create v0.3.0 --target main --title "Luna 0.3.0" --notes-file notes.md`}</code></pre>
            </CodeFile>
            <p>The workflows attach the apps and push the image when they finish.</p>
          </Step>
          <Step num="4" title="First release only">
            <p>Make the container package public: repo → Packages → luna → Package settings → Change visibility → Public.</p>
          </Step>
        </Steps>
      </section>

      <section>
        <h2 id="local">Building locally</h2>
        <p>All build output goes under <code>dist/&lt;target&gt;/</code> and is never committed.</p>
        <CodeFile label="terminal">
          <pre><code>{`npm run build:desktop    # dist/desktop/Luna-Setup-<version>.exe
npm run build:mobile     # syncs the web build into interfaces/mobile (then Android Studio / Xcode)
docker build -t luna .   # the container image`}</code></pre>
        </CodeFile>
      </section>

      <section>
        <h2 id="notes">Signing notes</h2>
        <Callout type="note" title="Unsigned builds">
          <p>
            The Windows installer isn't code-signed, so SmartScreen warns on first run ("More info → Run anyway").
            The Android APK is debug-signed for sideloading, and the iOS build runs in the simulator only. Store
            releases need signing certificates added to the workflow.
          </p>
        </Callout>
      </section>
    </DocsLayout>
  );
}
