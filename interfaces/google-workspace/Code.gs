// ── Luna AI — Google Workspace Add-on ────────────────────────────────────────
// Entry points for Docs, Sheets, and Slides.
// All chat logic lives in Luna.gs; UI helpers in Sidebar.html.

// ── Homepage triggers ─────────────────────────────────────────────────────────

function onHomepage(e) {
  return buildSidebarCard('document');
}

function onDocsHomepage(e) {
  return buildSidebarCard('document');
}

function onSheetsHomepage(e) {
  return buildSidebarCard('spreadsheet');
}

function onSlidesHomepage(e) {
  return buildSidebarCard('presentation');
}

function onFileScopeGranted(e) {
  return buildSidebarCard('document');
}

// ── Settings ──────────────────────────────────────────────────────────────────

function openSettings(e) {
  const card = CardService.newCardBuilder()
    .setName('Luna Settings')
    .setHeader(CardService.newCardHeader().setTitle('Luna AI Settings').setSubtitle('Configure server connection'))
    .addSection(
      CardService.newCardSection()
        .addWidget(CardService.newTextInput()
          .setFieldName('luna_url')
          .setTitle('Luna server URL')
          .setValue(getSettings().url)
          .setHint('e.g. http://localhost:8899 or https://your-luna.example.com'))
        .addWidget(CardService.newTextInput()
          .setFieldName('luna_token')
          .setTitle('Auth token (business variant only)')
          .setValue(getSettings().token)
          .setHint('Leave blank for personal variant'))
        .addWidget(CardService.newTextButton()
          .setText('Save settings')
          .setOnClickAction(CardService.newAction().setFunctionName('saveSettingsAction')))
        .addWidget(CardService.newTextButton()
          .setText('Test connection')
          .setOnClickAction(CardService.newAction().setFunctionName('testConnectionAction')))
    )
    .build();

  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().pushCard(card))
    .build();
}

function saveSettingsAction(e) {
  const url   = e.formInput.luna_url   || 'http://localhost:8899';
  const token = e.formInput.luna_token || '';
  const props = PropertiesService.getUserProperties();
  props.setProperty('LUNA_URL',   url);
  props.setProperty('LUNA_TOKEN', token);

  return CardService.newActionResponseBuilder()
    .setNavigation(CardService.newNavigation().popCard())
    .setNotification(CardService.newNotification().setText('Settings saved.'))
    .build();
}

function testConnectionAction(e) {
  const s = getSettings();
  try {
    const opts = { muteHttpExceptions: true, headers: {} };
    if (s.token) opts.headers['Authorization'] = 'Bearer ' + s.token;
    const r = UrlFetchApp.fetch(s.url + '/api/chat/conversations', opts);
    const msg = r.getResponseCode() === 200 ? 'Connected ✓' : 'HTTP ' + r.getResponseCode();
    return CardService.newActionResponseBuilder()
      .setNotification(CardService.newNotification().setText(msg))
      .build();
  } catch (err) {
    return CardService.newActionResponseBuilder()
      .setNotification(CardService.newNotification().setText('Connection failed: ' + err.message))
      .build();
  }
}

function newConversation(e) {
  PropertiesService.getUserProperties().deleteProperty('LUNA_CONV_ID');
  return CardService.newActionResponseBuilder()
    .setNotification(CardService.newNotification().setText('New conversation started.'))
    .build();
}

// ── Main card: sidebar with chat iframe ───────────────────────────────────────

function buildSidebarCard(hostType) {
  const html = HtmlService.createTemplateFromFile('Sidebar');
  html.hostType  = hostType;
  html.lunaUrl   = getSettings().url;
  html.lunaToken = getSettings().token;
  html.convId    = getConvId() || '';

  const output = html.evaluate()
    .setWidth(380)
    .setHeight(600)
    .setSandboxMode(HtmlService.SandboxMode.IFRAME);

  const card = CardService.newCardBuilder()
    .setName('Luna Chat')
    .setHeader(CardService.newCardHeader()
      .setTitle('Luna AI')
      .setSubtitle(hostType.charAt(0).toUpperCase() + hostType.slice(1)))
    .addSection(
      CardService.newCardSection()
        .addWidget(CardService.newDecoratedText()
          .setText('Chat with Luna below ↓')
          .setBottomLabel('Selection is passed automatically when you click "Use Selection"'))
        .addWidget(CardService.newHtmlWidget()
          .setHtml(output.getContent()))
    )
    .build();

  return card;
}

// ── Server-side Luna API call (called from Sidebar via google.script.run) ─────

function chatWithLuna(message, hostType) {
  const s = getSettings();
  const convId = getConvId();

  const payload = { message: message };
  if (convId) payload.conversation_id = parseInt(convId);

  const opts = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true,
    headers: {},
  };
  if (s.token) opts.headers['Authorization'] = 'Bearer ' + s.token;

  try {
    const res  = UrlFetchApp.fetch(s.url + '/api/chat/stream', opts);
    const body = res.getContentText();

    // Parse SSE response — collect all token events
    let full  = '';
    let newId = null;
    const lines = body.split('\n');
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try {
        const evt = JSON.parse(line.slice(6));
        if (evt.type === 'token')  full  += evt.content;
        if (evt.type === 'done' && evt.conversation_id) newId = evt.conversation_id;
      } catch (_) {}
    }

    if (newId) setConvId(newId);
    return { ok: true, text: full || '(no response)' };
  } catch (err) {
    return { ok: false, error: err.message };
  }
}

// ── Document content helpers (called from Sidebar via google.script.run) ──────

function getSelectionText() {
  try {
    const doc = DocumentApp.getActiveDocument();
    if (!doc) return '';
    const sel = doc.getSelection();
    if (!sel) return '';
    return sel.getRangeElements()
      .map(el => el.getElement().asText ? el.getElement().asText().getText() : '')
      .join(' ')
      .slice(0, 2000);
  } catch (_) { return ''; }
}

function getSheetSelection() {
  try {
    const ss    = SpreadsheetApp.getActiveSpreadsheet();
    const range = ss.getActiveRange();
    if (!range) return '';
    const vals = range.getValues();
    return vals.slice(0, 20).map(r => r.join('\t')).join('\n').slice(0, 2000);
  } catch (_) { return ''; }
}

function getSlideSelection() {
  try {
    const pres = SlidesApp.getActivePresentation();
    const slide = pres.getSelection().getCurrentPage();
    const texts = slide.getPageElements()
      .filter(el => el.getPageElementType() === SlidesApp.PageElementType.SHAPE)
      .map(el => el.asShape().getText().asString())
      .join('\n');
    return texts.slice(0, 2000);
  } catch (_) { return ''; }
}

function getDocumentSummary() {
  try {
    const doc  = DocumentApp.getActiveDocument();
    return doc ? doc.getBody().getText().slice(0, 3000) : '';
  } catch (_) { return ''; }
}

function getSheetSummary() {
  try {
    const ss    = SpreadsheetApp.getActiveSpreadsheet();
    const sheet = ss.getActiveSheet();
    const range = sheet.getDataRange();
    const vals  = range.getValues().slice(0, 50);
    return vals.map(r => r.join('\t')).join('\n').slice(0, 3000);
  } catch (_) { return ''; }
}

function insertTextAtCursor(text) {
  try {
    const doc = DocumentApp.getActiveDocument();
    if (!doc) return { ok: false, error: 'No active document' };
    const cursor = doc.getCursor();
    if (cursor) {
      cursor.insertText(text);
    } else {
      doc.getBody().appendParagraph(text);
    }
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

function insertCellValue(text) {
  try {
    const ss    = SpreadsheetApp.getActiveSpreadsheet();
    const range = ss.getActiveRange();
    range.setValue(text);
    return { ok: true };
  } catch (e) {
    return { ok: false, error: e.message };
  }
}

// ── Internal helpers ──────────────────────────────────────────────────────────

function getSettings() {
  const props = PropertiesService.getUserProperties();
  return {
    url:   props.getProperty('LUNA_URL')   || 'http://localhost:8899',
    token: props.getProperty('LUNA_TOKEN') || '',
  };
}
function getConvId() {
  return PropertiesService.getUserProperties().getProperty('LUNA_CONV_ID') || null;
}
function setConvId(id) {
  PropertiesService.getUserProperties().setProperty('LUNA_CONV_ID', String(id));
}
