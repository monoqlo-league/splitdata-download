// ゲームデータのアップロード(upload2.html)の中継スクリプト。
// ページから届いたCSVを、合言葉を確かめてから GitHub のリポジトリに書き込む。
// GitHub のトークンと合言葉は、このスクリプトの「スクリプト プロパティ」にだけ置く(ページやリポジトリには書かない)。
//
// 置き方(手順は README.md の「アップロードページ(合言葉版)」):
//   1. https://script.google.com で新しいプロジェクトを作り、このファイルの中身を貼る。
//   2. 「プロジェクトの設定」→「スクリプト プロパティ」に次の2つを足す。
//        GITHUB_TOKEN … monoqlo-data と event-data の Contents を Read and write にした fine-grained トークン
//        UPLOAD_PASS  … 管理者で共有する合言葉
//   3. 「デプロイ」→「新しいデプロイ」→「ウェブアプリ」。実行するユーザーは「自分」、アクセスできるユーザーは「全員」。
//   4. 出たURLを config.js の uploadEndpoint に貼る。

const OWNER = 'monoqlo-league';
// 書き込んでよいリポジトリと、置いてよいファイル名
const ALLOW = {
  'monoqlo-data': [/^\d{6}\.csv$/, /^summary\/\d{6}-summary\.csv$/],
  'event-data': [/^\d{8}-games\d+\.csv$/, /^summary\/\d{8}-games\d+-summary\.csv$/],
};
const MAX_FAILS = 5;          // 合言葉をこの回数まちがえると
const LOCK_SECONDS = 600;     // この秒数、受け付けない

function doGet() {
  return json_({ ok: true, service: 'monoqlo-upload' });
}

function doPost(e) {
  let body;
  try {
    body = JSON.parse(e.postData.contents);
  } catch (error) {
    return json_({ ok: false, error: 'bad-request' });
  }
  const props = PropertiesService.getScriptProperties();
  const pass = props.getProperty('UPLOAD_PASS');
  const token = props.getProperty('GITHUB_TOKEN');
  if (!pass || !token) return json_({ ok: false, error: 'not-configured' });

  // 合言葉の総当たりを防ぐ: まちがいが続いたら、しばらく受け付けない
  const cache = CacheService.getScriptCache();
  const fails = Number(cache.get('fails') || 0);
  if (fails >= MAX_FAILS) return json_({ ok: false, error: 'locked' });
  if (String((body && body.pass) || '') !== pass) {
    cache.put('fails', String(fails + 1), LOCK_SECONDS);
    Utilities.sleep(1000);
    return json_({ ok: false, error: 'wrong-pass' });
  }

  if (body.op === 'check') return json_({ ok: true });
  if (body.op !== 'commit') return json_({ ok: false, error: 'bad-request' });

  const repo = String(body.repo || '');
  const files = Array.isArray(body.files) ? body.files : [];
  if (!ALLOW[repo] || !files.length) return json_({ ok: false, error: 'invalid' });
  for (const f of files) {
    if (!f || typeof f.path !== 'string' || typeof f.content !== 'string' || !ALLOW[repo].some((re) => re.test(f.path))) {
      return json_({ ok: false, error: 'invalid', path: f && f.path });
    }
  }
  const message = String(body.message || 'アップロードページから更新').slice(0, 200);

  // 同時に届いても、1件ずつ書く
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(30000);
  } catch (error) {
    return json_({ ok: false, error: 'busy' });
  }
  try {
    const commit = commit_(token, repo, files, message);
    return json_({ ok: true, url: commit.html_url, sha: commit.sha });
  } catch (error) {
    return json_({ ok: false, error: 'github', detail: String(error.message || error).slice(0, 300) });
  } finally {
    lock.releaseLock();
  }
}

// ファイルをまとめて1つのコミットにする(途中で別の更新が入ったら、やり直す)
function commit_(token, repo, files, message) {
  for (let attempt = 0; attempt < 3; attempt++) {
    const ref = gh_(token, 'GET', `/repos/${OWNER}/${repo}/git/ref/heads/main`);
    const base = gh_(token, 'GET', `/repos/${OWNER}/${repo}/git/commits/${ref.object.sha}`);
    const tree = files.map((f) => {
      const blob = gh_(token, 'POST', `/repos/${OWNER}/${repo}/git/blobs`, { content: f.content, encoding: 'base64' });
      return { path: f.path, mode: '100644', type: 'blob', sha: blob.sha };
    });
    const nt = gh_(token, 'POST', `/repos/${OWNER}/${repo}/git/trees`, { base_tree: base.tree.sha, tree });
    const c = gh_(token, 'POST', `/repos/${OWNER}/${repo}/git/commits`, { message, tree: nt.sha, parents: [ref.object.sha] });
    try {
      gh_(token, 'PATCH', `/repos/${OWNER}/${repo}/git/refs/heads/main`, { sha: c.sha });
      return c;
    } catch (error) {
      if (attempt === 2) throw error;
    }
  }
}

function gh_(token, method, path, payload) {
  const res = UrlFetchApp.fetch('https://api.github.com' + path, {
    method: method.toLowerCase(),
    headers: { Authorization: 'Bearer ' + token, Accept: 'application/vnd.github+json', 'X-GitHub-Api-Version': '2022-11-28' },
    contentType: 'application/json',
    payload: payload ? JSON.stringify(payload) : undefined,
    muteHttpExceptions: true,
  });
  const code = res.getResponseCode();
  if (code >= 300) throw new Error(`GitHub ${code}: ${res.getContentText().slice(0, 200)}`);
  return JSON.parse(res.getContentText());
}

function json_(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj)).setMimeType(ContentService.MimeType.JSON);
}
