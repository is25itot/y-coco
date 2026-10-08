// y-coco 共通スクリプト
document.addEventListener("DOMContentLoaded", function () {
  // コメント欄: 文章が長くなったら下方向に伸ばす
  document.querySelectorAll("textarea[data-autogrow]").forEach(function (ta) {
    var grow = function () {
      ta.style.height = "auto";
      ta.style.height = ta.scrollHeight + "px";
    };
    ta.addEventListener("input", grow);
    grow();
  });

  // 画像選択: プレビュー表示 (1MB 超は選択時に警告)
  document.querySelectorAll("input[type=file][data-preview]").forEach(function (input) {
    var img = document.getElementById(input.dataset.preview);
    input.addEventListener("change", function () {
      var file = input.files && input.files[0];
      if (!file) { if (img) img.style.display = "none"; return; }
      if (file.size > 1024 * 1024) {
        alert("画像は1MBまでです。別の画像を選んでください。");
        input.value = "";
        if (img) img.style.display = "none";
        return;
      }
      if (img) {
        img.src = URL.createObjectURL(file);
        img.style.display = "block";
      }
    });
  });

  // フラッシュメッセージ(成功)は数秒後に消す
  document.querySelectorAll(".flash.success, .flash.message").forEach(function (el) {
    setTimeout(function () { el.style.display = "none"; }, 4000);
  });
});