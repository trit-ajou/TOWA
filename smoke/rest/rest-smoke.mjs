const config = {
  uiOrigin: env('UI_ORIGIN', 'http://localhost:5173'),
  uiEngineUrl: env('UI_ENGINE_URL', 'http://localhost:5173'),
  serviceEngineUrl: env('SERVICE_ENGINE_URL', 'http://localhost:8000'),
  modelEngineUrl: env('MODEL_ENGINE_URL', 'http://localhost:8100'),
}

const alphabet = '0123456789ABCDEFGHJKMNPQRSTVWXYZ'
const runId = String(Date.now())
const email = `rest-smoke-${runId}@example.test`
const projectId = ulid(Date.now(), 1)
const pageId = ulid(Date.now(), 2)
const createdProjects = []
const createdPages = []
const results = []
let sessionKey = null
const thumbnailPngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=='

main().catch(async (error) => {
  console.error('SMOKE_FAILED')
  console.error(error instanceof Error ? error.stack : error)
  await cleanup()
  process.exit(1)
})

async function main() {
  await waitForJson(`${config.serviceEngineUrl}/healthz`, (payload) => payload.status === 'ok')
  await waitForJson(`${config.modelEngineUrl}/healthz`, (payload) => payload.status === 'ok')
  await waitForUi()

  await verifyInfra()
  await verifyAuth()
  await verifyDirectUsage()
  await verifyProjectPages()
  await verifyModelBridge()
  await verifyModelJobs()
  await cleanup()

  console.log(`SUMMARY ok=${results.length} email=${email} project=${projectId} page=${pageId}`)
}

async function verifyInfra() {
  const uiResponse = await fetchWithTimeout(`${config.uiEngineUrl}/`)
  assertStatus(uiResponse, 200, 'GET UI /')
  const html = await uiResponse.text()
  assert(html.includes('<div id="app"></div>'), 'UI root did not include app mount')
  record('ui-engine GET /', '200')

  const serviceHealth = await requestJson('service', '/healthz')
  assertEqual(serviceHealth.status, 'ok', 'service health')
  record('service-engine GET /healthz', JSON.stringify(serviceHealth))

  const modelHealth = await requestJson('model', '/healthz')
  assertEqual(modelHealth.status, 'ok', 'model health')
  record('model-engine GET /healthz', JSON.stringify(modelHealth))
}

async function verifyAuth() {
  await preflight('service', '/auth/dev/login', 'POST', ['content-type'])
  const login = await requestJson('service', '/auth/dev/login', {
    method: 'POST',
    body: {
      email,
      nickname: 'REST Smoke',
    },
  })
  sessionKey = requiredString(login.session_key, 'session_key')
  assertEqual(login.user.email, email, 'login email')
  assertEqual(login.credit_balance, 1000, 'initial credit balance')
  record('service-engine POST /auth/dev/login', `session=${sessionKey.slice(0, 12)}...`)

  await preflight('service', '/auth/me', 'GET', ['authorization'])
  const me = await requestJson('service', '/auth/me', {
    token: sessionKey,
  })
  assertEqual(me.user.email, email, 'auth/me email')
  assertEqual(me.reserved_units, 0, 'initial reserved units')
  record('service-engine GET /auth/me', `credits=${me.credit_balance} reserved=${me.reserved_units}`)
}

async function verifyDirectUsage() {
  const captureCreate = await createServiceUsageJob({
    idempotencyKey: `direct-capture:${runId}`,
    operationKind: 'mask',
    requestRef: `smoke/direct/capture/${runId}`,
    estimatedUnits: 5,
  })
  const captureJobId = captureCreate.job_id
  assertEqual(captureCreate.status, 'authorized', 'direct usage capture create status')
  record('service-engine POST /usage/jobs capture fixture', captureJobId)

  const captureBefore = await getServiceUsageJob(captureJobId)
  assertEqual(captureBefore.status, 'authorized', 'direct usage capture before status')
  record('service-engine GET /usage/jobs/{job_id} authorized', captureBefore.status)

  await preflight('service', `/usage/jobs/${captureJobId}/capture`, 'POST', ['authorization', 'content-type'])
  const captured = await requestJson('service', `/usage/jobs/${captureJobId}/capture`, {
    method: 'POST',
    token: sessionKey,
    body: {},
  })
  assertEqual(captured.status, 'succeeded', 'direct usage capture status')
  assertEqual(captured.hold_status, 'captured', 'direct usage capture hold status')
  record('service-engine POST /usage/jobs/{job_id}/capture', captured.status)

  const captureAfter = await getServiceUsageJob(captureJobId)
  assertEqual(captureAfter.status, 'succeeded', 'direct usage capture after status')
  record('service-engine GET /usage/jobs/{job_id} captured', captureAfter.hold_status)

  const releaseCreate = await createServiceUsageJob({
    idempotencyKey: `direct-release:${runId}`,
    operationKind: 'translate',
    requestRef: `smoke/direct/release/${runId}`,
    estimatedUnits: 7,
  })
  const releaseJobId = releaseCreate.job_id
  assertEqual(releaseCreate.status, 'authorized', 'direct usage release create status')
  record('service-engine POST /usage/jobs release fixture', releaseJobId)

  await preflight('service', `/usage/jobs/${releaseJobId}/release`, 'POST', ['authorization', 'content-type'])
  const released = await requestJson('service', `/usage/jobs/${releaseJobId}/release`, {
    method: 'POST',
    token: sessionKey,
    body: {
      error_code: 'rest_smoke_released',
      reason: 'REST smoke release path',
    },
  })
  assertEqual(released.status, 'failed', 'direct usage release status')
  assertEqual(released.hold_status, 'released', 'direct usage release hold status')
  assertEqual(released.error_code, 'rest_smoke_released', 'direct usage release error code')
  record('service-engine POST /usage/jobs/{job_id}/release', released.status)

  const releaseAfter = await getServiceUsageJob(releaseJobId)
  assertEqual(releaseAfter.status, 'failed', 'direct usage release after status')
  record('service-engine GET /usage/jobs/{job_id} released', releaseAfter.hold_status)
}

async function verifyProjectPages() {
  await preflight('service', '/api/v1/projects', 'POST', ['authorization', 'content-type'])
  const project = await requestJson('service', '/api/v1/projects', {
    method: 'POST',
    token: sessionKey,
    body: {
      id: projectId,
      name: 'REST Smoke Project',
      thumbnail_url: null,
      source_lang: 'ja',
      target_lang: 'ko',
      status: 'todo',
      folder_id: null,
      config: {
        auto_detect: true,
      },
    },
  })
  createdProjects.push(projectId)
  assertEqual(project.id, projectId, 'project id')
  assertEqual(project.page_count, 0, 'project initial page count')
  record('service-engine POST /api/v1/projects', project.id)

  await preflight('service', '/api/v1/projects', 'GET', ['authorization'])
  const projects = await requestJson('service', '/api/v1/projects', {
    token: sessionKey,
  })
  assert(projects.items.some((item) => item.id === projectId), 'created project was not listed')
  record('service-engine GET /api/v1/projects', `items=${projects.items.length}`)

  await preflight('service', `/api/v1/projects/${projectId}`, 'GET', ['authorization'])
  const projectDetail = await requestJson('service', `/api/v1/projects/${projectId}`, {
    token: sessionKey,
  })
  assertEqual(projectDetail.id, projectId, 'project detail id')
  record('service-engine GET /api/v1/projects/{project_id}', projectDetail.status)

  await preflight('service', `/api/v1/projects/${projectId}`, 'PATCH', ['authorization', 'content-type'])
  const patched = await requestJson('service', `/api/v1/projects/${projectId}`, {
    method: 'PATCH',
    token: sessionKey,
    body: {
      status: 'in-progress',
      thumbnail_url: 'https://storage.example.test/smoke/project.webp',
    },
  })
  assertEqual(patched.status, 'in-progress', 'project patched status')
  record('service-engine PATCH /api/v1/projects/{project_id}', patched.status)

  await preflight('service', `/api/v1/projects/${projectId}/pages`, 'GET', ['authorization'])
  const emptyPages = await requestJson('service', `/api/v1/projects/${projectId}/pages`, {
    token: sessionKey,
  })
  assertEqual(emptyPages.items.length, 0, 'initial project pages')
  record('service-engine GET /api/v1/projects/{project_id}/pages empty', `items=${emptyPages.items.length}`)

  await preflight('service', `/api/v1/projects/${projectId}/pages`, 'POST', ['authorization'])
  const pageCreate = await requestRaw('service', `/api/v1/projects/${projectId}/pages`, {
    method: 'POST',
    token: sessionKey,
    body: snapshotForm('waiting'),
  }).then((response) => response.json())
  createdPages.push(pageId)
  assertEqual(pageCreate.page.id, pageId, 'created page id')
  assertEqual(pageCreate.page.index, 1, 'created page index')
  record('service-engine POST /api/v1/projects/{project_id}/pages', pageCreate.page.id)

  const pages = await requestJson('service', `/api/v1/projects/${projectId}/pages`, {
    token: sessionKey,
  })
  assert(pages.items.some((item) => item.id === pageId), 'created page was not listed')
  record('service-engine GET /api/v1/projects/{project_id}/pages populated', `items=${pages.items.length}`)

  await preflight('service', `/api/v1/pages/${pageId}/thumbnail`, 'GET', ['authorization'])
  const thumbnail = await requestRaw('service', `/api/v1/pages/${pageId}/thumbnail`, {
    token: sessionKey,
  })
  assertEqual(thumbnail.headers.get('content-type'), 'image/webp', 'thumbnail content type')
  record('service-engine GET /api/v1/pages/{page_id}/thumbnail', thumbnail.headers.get('content-type'))

  await preflight('service', `/api/v1/pages/${pageId}/snapshot`, 'GET', ['authorization'])
  const snapshot = await requestRaw('service', `/api/v1/pages/${pageId}/snapshot`, {
    token: sessionKey,
  })
  const snapshotType = snapshot.headers.get('content-type') || ''
  assert(snapshotType.startsWith('multipart/'), `unexpected snapshot content type: ${snapshotType}`)
  record('service-engine GET /api/v1/pages/{page_id}/snapshot', snapshotType)

  await preflight('service', `/api/v1/pages/${pageId}/snapshot`, 'PUT', ['authorization'])
  const update = await requestRaw('service', `/api/v1/pages/${pageId}/snapshot`, {
    method: 'PUT',
    token: sessionKey,
    body: snapshotForm('done'),
  }).then((response) => response.json())
  assertEqual(update.page.status, 'done', 'updated page status')
  record('service-engine PUT /api/v1/pages/{page_id}/snapshot', update.page.status)
}

async function verifyModelBridge() {
  const bridgeHealth = await requestJson('model', '/bridge/service/healthz')
  assertEqual(bridgeHealth.status, 'ok', 'bridge health status')
  assertEqual(bridgeHealth.service.status, 'ok', 'bridge service health status')
  record('model-engine GET /bridge/service/healthz', JSON.stringify(bridgeHealth.service))

  await preflight('model', '/bridge/service/auth/me', 'GET', ['authorization'])
  const bridgeMe = await requestJson('model', '/bridge/service/auth/me', {
    token: sessionKey,
  })
  assertEqual(bridgeMe.user.email, email, 'bridge auth/me email')
  record('model-engine GET /bridge/service/auth/me', bridgeMe.user.email)

  const bridgeCapture = await createBridgeUsageJob({
    idempotencyKey: `bridge-capture:${runId}`,
    operationKind: 'inpaint',
    requestRef: `smoke/bridge/capture/${runId}`,
    estimatedUnits: 3,
  })
  const bridgeCaptureJobId = bridgeCapture.job_id
  assertEqual(bridgeCapture.status, 'authorized', 'bridge capture create status')
  record('model-engine POST /bridge/service/usage/jobs capture fixture', bridgeCaptureJobId)

  await preflight('model', `/bridge/service/usage/jobs/${bridgeCaptureJobId}/capture`, 'POST', ['authorization', 'content-type'])
  const bridgeCaptured = await requestJson('model', `/bridge/service/usage/jobs/${bridgeCaptureJobId}/capture`, {
    method: 'POST',
    token: sessionKey,
    body: {},
  })
  assertEqual(bridgeCaptured.status, 'succeeded', 'bridge capture status')
  assertEqual(bridgeCaptured.hold_status, 'captured', 'bridge capture hold status')
  record('model-engine POST /bridge/service/usage/jobs/{job_id}/capture', bridgeCaptured.status)

  await preflight('model', `/bridge/service/usage/jobs/${bridgeCaptureJobId}`, 'GET', ['authorization'])
  const bridgeCaptureGet = await requestJson('model', `/bridge/service/usage/jobs/${bridgeCaptureJobId}`, {
    token: sessionKey,
  })
  assertEqual(bridgeCaptureGet.status, 'succeeded', 'bridge capture get status')
  record('model-engine GET /bridge/service/usage/jobs/{job_id} captured', bridgeCaptureGet.hold_status)

  const bridgeRelease = await createBridgeUsageJob({
    idempotencyKey: `bridge-release:${runId}`,
    operationKind: 'mask',
    requestRef: `smoke/bridge/release/${runId}`,
    estimatedUnits: 4,
  })
  const bridgeReleaseJobId = bridgeRelease.job_id
  assertEqual(bridgeRelease.status, 'authorized', 'bridge release create status')
  record('model-engine POST /bridge/service/usage/jobs release fixture', bridgeReleaseJobId)

  await preflight('model', `/bridge/service/usage/jobs/${bridgeReleaseJobId}/release`, 'POST', ['authorization', 'content-type'])
  const bridgeReleased = await requestJson('model', `/bridge/service/usage/jobs/${bridgeReleaseJobId}/release`, {
    method: 'POST',
    token: sessionKey,
    body: {
      error_code: 'rest_smoke_bridge_released',
      reason: 'REST smoke bridge release path',
    },
  })
  assertEqual(bridgeReleased.status, 'failed', 'bridge release status')
  assertEqual(bridgeReleased.hold_status, 'released', 'bridge release hold status')
  record('model-engine POST /bridge/service/usage/jobs/{job_id}/release', bridgeReleased.status)

  const bridgeReleaseGet = await requestJson('model', `/bridge/service/usage/jobs/${bridgeReleaseJobId}`, {
    token: sessionKey,
  })
  assertEqual(bridgeReleaseGet.status, 'failed', 'bridge release get status')
  record('model-engine GET /bridge/service/usage/jobs/{job_id} released', bridgeReleaseGet.hold_status)
}

async function verifyModelJobs() {
  await preflight('model', '/v1/jobs', 'POST', ['authorization', 'content-type'])
  for (const operationKind of ['detect', 'translate', 'inpaint']) {
    const create = await requestJson('model', '/v1/jobs', {
      method: 'POST',
      token: sessionKey,
      body: modelJobPayload(operationKind),
    })
    assertEqual(create.status, 'queued', `model ${operationKind} create status`)
    assertEqual(create.operation_kind, operationKind, `model ${operationKind} operation`)
    record(`model-engine POST /v1/jobs ${operationKind}`, create.job_id)

    await preflight('model', `/v1/jobs/${create.job_id}`, 'GET', ['authorization'])
    const terminal = await waitForModelJob(create.job_id)
    assertEqual(terminal.status, 'succeeded', `model ${operationKind} terminal status`)
    assert(terminal.stage_reports.length > 0, `model ${operationKind} missing stage reports`)
    record(
      `model-engine GET /v1/jobs/{job_id} ${operationKind}`,
      `status=${terminal.status} stages=${terminal.stage_reports.map((stage) => stage.stage_name).join('/')}`,
    )
  }

  const afterJobs = await requestJson('service', '/auth/me', {
    token: sessionKey,
  })
  assert(afterJobs.credit_balance < 1000, 'credit balance did not decrease after captured jobs')
  assertEqual(afterJobs.reserved_units, 0, 'reserved units after model jobs')
  record('service-engine GET /auth/me after jobs', `credits=${afterJobs.credit_balance} reserved=${afterJobs.reserved_units}`)
}

async function cleanup() {
  if (!sessionKey) {
    return
  }

  while (createdPages.length > 0) {
    const id = createdPages.pop()
    try {
      await preflight('service', `/api/v1/pages/${id}`, 'DELETE', ['authorization'])
      const deleted = await requestJson('service', `/api/v1/pages/${id}`, {
        method: 'DELETE',
        token: sessionKey,
      })
      assertEqual(deleted.deleted, true, 'page cleanup deleted')
      record('service-engine DELETE /api/v1/pages/{page_id}', deleted.page_id)
    } catch (error) {
      console.error(`cleanup page ${id} failed: ${error.message}`)
    }
  }

  while (createdProjects.length > 0) {
    const id = createdProjects.pop()
    try {
      await preflight('service', `/api/v1/projects/${id}`, 'DELETE', ['authorization'])
      const deleted = await requestJson('service', `/api/v1/projects/${id}`, {
        method: 'DELETE',
        token: sessionKey,
      })
      assertEqual(deleted.deleted, true, 'project cleanup deleted')
      record('service-engine DELETE /api/v1/projects/{project_id}', deleted.project_id)
    } catch (error) {
      console.error(`cleanup project ${id} failed: ${error.message}`)
    }
  }
}

async function createServiceUsageJob({ idempotencyKey, operationKind, requestRef, estimatedUnits }) {
  await preflight('service', '/usage/jobs', 'POST', ['authorization', 'content-type'])
  return requestJson('service', '/usage/jobs', {
    method: 'POST',
    token: sessionKey,
    body: {
      idempotency_key: idempotencyKey,
      operation_kind: operationKind,
      request_ref: requestRef,
      estimated_units: estimatedUnits,
    },
  })
}

async function getServiceUsageJob(jobId) {
  await preflight('service', `/usage/jobs/${jobId}`, 'GET', ['authorization'])
  return requestJson('service', `/usage/jobs/${jobId}`, {
    token: sessionKey,
  })
}

async function createBridgeUsageJob({ idempotencyKey, operationKind, requestRef, estimatedUnits }) {
  await preflight('model', '/bridge/service/usage/jobs', 'POST', ['authorization', 'content-type'])
  return requestJson('model', '/bridge/service/usage/jobs', {
    method: 'POST',
    token: sessionKey,
    body: {
      idempotency_key: idempotencyKey,
      operation_kind: operationKind,
      request_ref: requestRef,
      estimated_units: estimatedUnits,
    },
  })
}

async function waitForModelJob(jobId) {
  const deadline = Date.now() + 15000
  let lastPayload = null
  while (Date.now() < deadline) {
    const payload = await requestJson('model', `/v1/jobs/${jobId}`, {
      token: sessionKey,
    })
    lastPayload = payload
    if (['succeeded', 'failed', 'partial'].includes(payload.status)) {
      return payload
    }
    await sleep(125)
  }
  throw new Error(`model job ${jobId} did not reach a terminal status; last=${JSON.stringify(lastPayload)}`)
}

async function waitForUi() {
  const deadline = Date.now() + 30000
  let lastError = null
  while (Date.now() < deadline) {
    try {
      const response = await fetchWithTimeout(`${config.uiEngineUrl}/`, {}, 2500)
      if (response.status === 200) {
        return
      }
      lastError = new Error(`status=${response.status}`)
    } catch (error) {
      lastError = error
    }
    await sleep(250)
  }
  throw new Error(`ui-engine did not become ready: ${lastError?.message ?? 'unknown error'}`)
}

async function waitForJson(url, predicate) {
  const deadline = Date.now() + 30000
  let lastError = null
  while (Date.now() < deadline) {
    try {
      const response = await fetchWithTimeout(url, {}, 2500)
      if (response.ok) {
        const payload = await response.json()
        if (predicate(payload)) {
          return payload
        }
        lastError = new Error(`predicate rejected ${JSON.stringify(payload)}`)
      } else {
        lastError = new Error(`status=${response.status}`)
      }
    } catch (error) {
      lastError = error
    }
    await sleep(250)
  }
  throw new Error(`${url} did not become ready: ${lastError?.message ?? 'unknown error'}`)
}

async function preflight(engine, path, method, requestHeaders = []) {
  const headers = {
    Origin: config.uiOrigin,
    'Access-Control-Request-Method': method,
  }
  if (requestHeaders.length > 0) {
    headers['Access-Control-Request-Headers'] = requestHeaders.join(', ')
  }
  const response = await fetchWithTimeout(urlFor(engine, path), {
    method: 'OPTIONS',
    headers,
  })
  assertStatus(response, 200, `OPTIONS ${engine} ${path}`)
  assertEqual(
    response.headers.get('access-control-allow-origin'),
    config.uiOrigin,
    `OPTIONS ${engine} ${path} CORS allow-origin`,
  )
  record(`${engine} OPTIONS ${path}`, method)
}

async function requestJson(engine, path, { method = 'GET', token, body, headers = {} } = {}) {
  const response = await requestRaw(engine, path, {
    method,
    token,
    body: body === undefined ? undefined : JSON.stringify(body),
    headers: {
      Accept: 'application/json',
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...headers,
    },
  })
  const raw = await response.text()
  const payload = raw.trim() ? JSON.parse(raw) : {}
  return payload
}

async function requestRaw(engine, path, { method = 'GET', token, body, headers = {} } = {}) {
  const requestHeaders = {
    Origin: config.uiOrigin,
    ...headers,
  }
  if (token) {
    requestHeaders.Authorization = `Bearer ${token}`
  }
  const response = await fetchWithTimeout(urlFor(engine, path), {
    method,
    headers: requestHeaders,
    body,
  })
  assertEqual(
    response.headers.get('access-control-allow-origin'),
    config.uiOrigin,
    `${method} ${engine} ${path} CORS allow-origin`,
  )
  if (!response.ok) {
    throw new Error(`${method} ${urlFor(engine, path)} failed ${response.status}: ${await response.text()}`)
  }
  return response
}

async function fetchWithTimeout(url, init = {}, timeoutMs = 10000) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await fetch(url, {
      ...init,
      signal: controller.signal,
    })
  } finally {
    clearTimeout(timeout)
  }
}

function snapshotForm(status) {
  const metadata = {
    page: {
      id: pageId,
      project_id: projectId,
      index: 1,
      status,
      text_blocks: [
        {
          id: 'tb_001',
          page_id: pageId,
          bbox: {
            x: 10,
            y: 20,
            width: 80,
            height: 40,
          },
          original: 'hello',
          translated: status === 'done' ? 'hello translated' : '',
        },
      ],
    },
  }
  const form = new FormData()
  form.append('metadata', new Blob([JSON.stringify(metadata)], { type: 'application/json' }), 'metadata.json')
  form.append('original_image', new Blob([new Uint8Array([137, 80, 78, 71, 13, 10])], { type: 'image/png' }), 'original.png')
  form.append('layer_blob', new Blob([new Uint8Array([1, 2, 3, 4])], { type: 'application/octet-stream' }), 'page.layer')
  form.append('thumbnail', new Blob([new Uint8Array(Buffer.from(thumbnailPngBase64, 'base64'))], { type: 'image/png' }), 'thumbnail.png')
  return form
}

function modelJobPayload(operationKind) {
  return {
    schema_version: 'v1',
    idempotency_key: `model-job:${runId}:op:${operationKind}:v:1`,
    operation_kind: operationKind,
    request_ref: `project/${projectId}/page/001/${operationKind}`,
    document: {
      id: `doc_${pageId}`,
      name: 'smoke-page-001',
      width: 800,
      height: 1200,
      layers: [
        {
          id: 'layer_original',
          name: 'Original',
          type: 'graphic',
          left: 0,
          top: 0,
          width: 800,
          height: 1200,
          source_ref: 'artifact://page-original',
        },
      ],
      text_blocks: [],
      stage_meta: {},
    },
    artifacts: {
      'artifact://page-original': {
        artifact_ref: 'artifact://page-original',
        kind: 'bitmap',
        media_type: 'image/png',
        uri: 'https://storage.example.test/smoke-page-001.png',
      },
    },
    runtime_context: {
      mode: 'saas',
      workspace_uri: `workspace://project/${projectId}/page/001/${operationKind}`,
      requested_by: email,
      target_regions: [],
      selected_layer_ids: [],
    },
  }
}

function urlFor(engine, path) {
  const baseUrl = engine === 'service'
    ? config.serviceEngineUrl
    : config.modelEngineUrl
  return `${baseUrl}${path}`
}

function env(name, fallback) {
  return process.env[name] || fallback
}

function ulid(timeMs, salt) {
  let time = BigInt(timeMs)
  let timePart = ''
  for (let index = 0; index < 10; index += 1) {
    timePart = alphabet[Number(time % 32n)] + timePart
    time /= 32n
  }

  let seed = BigInt(timeMs + salt * 2654435761)
  let randomPart = ''
  for (let index = 0; index < 16; index += 1) {
    seed = (seed * 1103515245n + 12345n + BigInt(salt)) & ((1n << 63n) - 1n)
    randomPart += alphabet[Number(seed % 32n)]
  }
  return timePart + randomPart
}

function requiredString(value, name) {
  assert(typeof value === 'string' && value.length > 0, `${name} must be a non-empty string`)
  return value
}

function assertStatus(response, expectedStatus, label) {
  assertEqual(response.status, expectedStatus, `${label} status`)
}

function assertEqual(actual, expected, label) {
  if (actual !== expected) {
    throw new Error(`${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`)
  }
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message)
  }
}

function record(name, detail) {
  results.push({ name, detail })
  console.log(`OK ${name}: ${detail}`)
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}
