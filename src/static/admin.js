import { initAdminMembers } from "./admin-members.js";
import { createAdminContext } from "./admin/page-context.js";
import { initCatalogEditor } from "./admin/catalog-editor.js";
import { initCatalogList } from "./admin/catalog-list.js";
import { initItemEvents } from "./admin/item-events.js";
import { setImage } from "./admin/item-images.js";

// 페이지 진입점에서는 기능을 조립하고 각 기능은 자신의 폼이 있을 때만 실행한다.
export function initAdminPage({ root, signal, navigate }) {
    const adminRoot = root.querySelector("#admin-view");
    const context = createAdminContext({ root: adminRoot, signal, navigate });

    initCatalogEditor(context);
    initCatalogList(context);
    initItemEvents(context);
    initAdminMembers(adminRoot, signal, navigate);

    for (const image of adminRoot.querySelectorAll("img[data-inventory-icon]")) {
        setImage(image, image.dataset.inventoryIcon);
    }
}
