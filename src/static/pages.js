import { initAuthSession } from "./auth-session.js";
import { initAdminPage } from "./admin.js";
import { initAuctionLive, initInventoryLive } from "./auction-live.js";
import { initWalletBalance } from "./wallet-balance.js";
import { initPlayPage, preparePlayPage } from "./game/main.js";
import { initOpeningPage } from "./game/opening.js";

// 페이지별 동작은 이 목록에 등록한다. HTML만 필요한 화면은 등록하지 않아도 된다.
const pageInitializers = {
    admin: initAdminPage,
    auction: initAuctionLive,
    inventory: initInventoryLive,
    play: initPlayPage,
    opening: initOpeningPage,
};

export function initializePage(context) {
    initAuthSession(context);
    initWalletBalance(context); // 헤더의 사용 가능 금액 (모든 화면 공통)

    const initialize = pageInitializers[document.body.dataset.page];
    if (context.prepared) {
        context.prepared.activate();
    } else if (initialize) {
        initialize(context);
    }
}

export function preparePage(context) {
    return context.page.body.dataset.page === "play" ? preparePlayPage(context) : null;
}
