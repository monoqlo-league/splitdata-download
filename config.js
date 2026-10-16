// ダウンロードの記録先。
// スプレッドシートに貼ったスクリプトを「ウェブアプリ」として公開したときのURL
// (https://script.google.com/macros/s/…/exec)を、下の "" の中に貼る。
// 空のままでもページは使えるが、誰が取得したかは記録されない。
window.SPLITDATA_CONFIG = {
  endpoint: "https://script.google.com/macros/s/AKfycbzjx9tXop-4FMulI-3YrrnXmNbuBb7bPJsQS_vvbxHmwhgMXJzqzeYIDUcHBxjlL2avAA/exec",
  // ゲームデータのアップロード(合言葉版 upload2.html)の中継。gas/Upload.gs をウェブアプリとして公開したURLを貼る。
  uploadEndpoint: "",
  // ゲームデータのアップロード(upload.html)の「GitHubでログイン」。GitHub App の Client ID と、gas/Login.gs を公開したURL。
  githubClientId: "",
  loginEndpoint: "",
};
