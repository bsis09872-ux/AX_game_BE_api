// 경매장 화면이 팝업(iframe) 안에 떠 있을 때 닫기를 바깥 화면에 알린다.
// 포커스가 iframe 안에 있으면 Esc가 바깥 <dialog>에 전달되지 않아서 여기서 메시지로 알려 준다.
// 바깥 화면은 { type: 'auction:close' } 메시지를 받으면 팝업을 닫는다.
(function () {
  if (window.parent === window) return; // 팝업이 아니면 아무것도 하지 않는다

  function requestClose() {
    window.parent.postMessage({ type: 'auction:close' }, window.location.origin);
  }

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') requestClose();
  });

  // data-auction-close가 붙은 버튼·링크를 누르면 닫는다
  document.addEventListener('click', function (event) {
    if (event.target.closest('[data-auction-close]')) {
      event.preventDefault();
      requestClose();
    }
  });
})();
