const synthetics = require('Synthetics');
const log = require('SyntheticsLogger');
const https = require('https');

const apiBase = process.env.API_BASE_URL;
const username = process.env.APP_USERNAME;
const password = process.env.APP_PASSWORD;
const tenantId = process.env.TENANT_ID || 'default';
const question = process.env.CHECK_QUESTION || 'Health check question from CloudWatch Synthetics';

function buildRequestOptions(method, path, token) {
  const url = new URL(apiBase);
  const headers = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  if (tenantId) {
    headers['X-Tenant-ID'] = tenantId;
  }

  return {
    protocol: url.protocol,
    hostname: url.hostname,
    port: url.port || (url.protocol === 'https:' ? 443 : 80),
    method,
    path,
    headers,
  };
}

function performRequest(stepName, method, path, token, payload) {
  const options = buildRequestOptions(method, path, token);

  return synthetics.executeHttpStep(stepName, options, (response) =>
    new Promise((resolve, reject) => {
      let body = '';
      response.on('data', (chunk) => {
        body += chunk;
      });
      response.on('end', () => {
        const statusCode = response.statusCode || 0;

        if (statusCode < 200 || statusCode >= 300) {
          reject(new Error(`Step ${stepName} failed with status ${statusCode}: ${body}`));
          return;
        }

        if (!body) {
          resolve({});
          return;
        }

        try {
          resolve(JSON.parse(body));
        } catch (error) {
          reject(new Error(`Step ${stepName} returned invalid JSON: ${error.message}`));
        }
      });
      response.on('error', reject);

      if (payload !== undefined && payload !== null) {
        response.req.write(JSON.stringify(payload));
      }
      response.req.end();
    })
  );
}

exports.handler = async () => {
  if (!apiBase || !username || !password) {
    throw new Error('Missing required environment variables: API_BASE_URL, APP_USERNAME, APP_PASSWORD');
  }

  const healthResponse = await performRequest('health-ready', 'GET', '/api/health/ready');
  log.info(`Health ready response: ${JSON.stringify(healthResponse)}`);

  const loginResponse = await performRequest('login', 'POST', '/api/auth/login', null, {
    username,
    password,
  });

  if (!loginResponse.access_token) {
    throw new Error(`Login response missing access_token: ${JSON.stringify(loginResponse)}`);
  }

  const token = loginResponse.access_token;

  const chatResponse = await performRequest('chat', 'POST', '/api/chat/', token, {
    question,
  });

  if (!chatResponse.status) {
    throw new Error(`Chat response missing status: ${JSON.stringify(chatResponse)}`);
  }

  if (chatResponse.status === 'pending_approval' && chatResponse.approval_id) {
    const approvalResult = await performRequest(
      'approval-result',
      'GET',
      `/api/approvals/${chatResponse.approval_id}/result`,
      token
    );

    if (!approvalResult.status) {
      throw new Error(`Approval result missing status: ${JSON.stringify(approvalResult)}`);
    }
  }

  log.info(`Canary run succeeded with chat status: ${chatResponse.status}`);
};
