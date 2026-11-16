const vscode = require('vscode');
const http = require('http');

let statusBarItem;
let pollTimer;

function activate(context) {
  statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBarItem.command = 'tokenGuard.openDashboard';
  statusBarItem.tooltip = 'Token Guard Proxy (http://localhost:8088/v1)\nClick to open live Dashboard';
  statusBarItem.text = '$(shield) Token Guard: Active';
  statusBarItem.color = '#00f0ff';
  statusBarItem.show();
  context.subscriptions.push(statusBarItem);

  const openCmd = vscode.commands.registerCommand('tokenGuard.openDashboard', () => {
    vscode.env.openExternal(vscode.Uri.parse('http://localhost:8088/dashboard'));
  });
  context.subscriptions.push(openCmd);

  function checkStatus() {
    const req = http.get('http://localhost:8088/metrics', { timeout: 1500 }, (res) => {
      if (res.statusCode === 200) {
        let raw = '';
        res.on('data', chunk => raw += chunk);
        res.on('end', () => {
          try {
            const data = JSON.parse(raw);
            const saved = data.today_tokens_saved || data.total_tokens_saved || 0;
            if (saved > 0) {
              statusBarItem.text = `$(shield) Token Guard: Active (+${saved.toLocaleString()} saved)`;
            } else {
              statusBarItem.text = `$(shield) Token Guard: Active`;
            }
            statusBarItem.color = '#00e676';
          } catch (_) {
            statusBarItem.text = `$(shield) Token Guard: Active`;
            statusBarItem.color = '#00f0ff';
          }
        });
      } else {
        statusBarItem.text = `$(shield) Token Guard: Port Error`;
        statusBarItem.color = '#ffb300';
      }
    });

    req.on('error', () => {
      statusBarItem.text = `$(shield) Token Guard: Offline`;
      statusBarItem.color = '#8492a6';
    });
  }

  checkStatus();
  pollTimer = setInterval(checkStatus, 3000);
}

function deactivate() {
  if (pollTimer) clearInterval(pollTimer);
}

module.exports = { activate, deactivate };
