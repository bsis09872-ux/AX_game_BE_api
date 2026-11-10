import { initAuthSession } from "./auth-session.js";
import { initAdminPage } from "./admin.js";
import { initAuctionLive } from "./auction-live.js";

// 페이지별 동작은 이 목록에 등록한다. HTML만 필요한 화면은 등록하지 않아도 된다.
const pageInitializers = {
    admin: initAdminPage,
    auction: initAuctionLive,
};

export function initializePage(context) {
    initAuthSession(context);

    const initialize = pageInitializers[document.body.dataset.page];
    if (initialize) {
        initialize(context);
    }
}
