// ゲームデータのアップロード(upload.html)の「GitHubでログイン」を仲立ちするスクリプト。
// GitHub のログイン画面から戻ってきた「コード」を、GitHub App の秘密の値を使ってトークンに替え、ページに返す。
// 秘密の値はこのスクリプトの「スクリプト プロパティ」にだけ置く(ページやリポジトリには書かない)。
//
// 置き方(手順は README.md の「アップロードページ(GitHubでログイン)」):
//   1. https://script.google.com で新しいプロジェクトを作り、このファイルの中身を貼る。
//   2. 「プロジェクトの設定」→「スクリプト プロパティ」に次の2つを足す。
//        CLIENT_ID     … GitHub App の Client ID
//        CLIENT_SECRET … GitHub App で作った Client secret
//   3. 「デプロイ」→「新しいデプロイ」→「ウェブアプリ」。実行するユーザーは「自分」、アクセスできるユーザーは「全員」。
//   4. 出たURLを config.js の loginEndpoint に貼る。

function doGet() {
  return json_({ ok: true, service: 'monoqlo-login' });
}

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (error) {
    return json_({ ok: false, error: 'bad-request' });
  }
  const props = PropertiesService.getScriptProperties();
  const id = props.getProperty('CLIENT_ID');
  const secret = props.getProperty('CLIENT_SECRET');
  if (!id || !secret) return json_({ ok: false, error: 'not-configured' });

  const code = String((body && body.code) || '');
  if (!/^[0-9a-f]{10,64}$/i.test(code)) return json_({ ok: false, error: 'invalid' });

  const res = UrlFetchApp.fetch('https://github.com/login/oauth/access_token', {
    method: 'post',
    headers: { Accept: 'application/json' },
    payload: { client_id: id, client_secret: secret, code },
    muteHttpExceptions: true,
  });
  let data = {};
  try {
    data = JSON.parse(res.getContentText());
  } catch (error) {
    return json_({ ok: false, error: 'github', detail: 'HTTP ' + res.getResponseCode() });
  }
  if (!data.access_token) return json_({ ok: false, error: data.error || 'github', detail: data.error_description || '' });
  // expires_in(秒)は GitHub App のトークンの有効期限(ふつう8時間)
  return json_({ ok: true, token: data.access_token, expiresIn: data.expires_in || null });
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
