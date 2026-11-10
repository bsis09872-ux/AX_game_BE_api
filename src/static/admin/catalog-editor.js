import { setImage } from "./item-images.js";

const imageNames = {
    fish_carp: "붕어",
    fish_mackerel: "고등어",
    fish_bass: "농어",
    fish_salmon: "연어",
    fish_puffer: "복어",
    fish_golden: "황금 잉어",
    fish_dragon: "바다용",
    gem_pearl: "진주",
    gem_sapphire: "사파이어",
    gem_black_pearl: "흑진주",
    misc_boot: "낡은 장화",
    misc_seaweed: "해초",
    misc_bottle: "편지병",
    gift_box: "선물 상자",
    choco_stick: "초코 스틱",
    berry_stick: "베리 스틱",
};

// 카탈로그 입력, 미리보기와 이미지 업로드를 담당한다.
export function initCatalogEditor(context) {
    const { getElement, request, run, navigate } = context;
    const editor = getElement("catalog-editor");
    if (!editor) {
        return;
    }

    const editingId = editor.dataset.editId || null;

    function updatePreview() {
        const fields = editor.elements;
        getElement("preview-name").textContent = fields.name.value || "새 아이템";
        getElement("preview-category").textContent = fields.category.value;
        getElement("preview-rarity").textContent = fields.rarity.value;
        getElement("preview-frame").dataset.rarity = fields.rarity.value;
        getElement("preview-description").textContent =
            fields.description.value || "설명을 입력해 주세요.";
        getElement("preview-price").textContent =
            `${Number(fields.start_price.value || 0).toLocaleString("ko-KR")} GOLD`;
        getElement("preview-fishable").textContent = fields.fishable.checked ? "가능" : "불가";
        setImage(getElement("preview-image"), fields.icon.value);
        for (const button of getElement("image-gallery").querySelectorAll("button")) {
            button.setAttribute("aria-pressed", String(button.dataset.icon === fields.icon.value));
        }
    }

    async function loadImages() {
        const images = await request("/admin/item-images");
        getElement("image-gallery").replaceChildren();

        for (const item of images) {
            const button = document.createElement("button");
            button.type = "button";
            button.dataset.icon = item.icon;
            const label = imageNames[item.icon] || `업로드 ${item.icon.slice(-6)}`;
            button.title = label;
            button.setAttribute("aria-label", label);

            const image = document.createElement("img");
            image.alt = "";
            image.src = item.url;

            const name = document.createElement("span");
            name.textContent = label;

            button.append(image, name);
            button.addEventListener("click", () => {
                editor.elements.icon.value = item.icon;
                updatePreview();
            });
            getElement("image-gallery").append(button);
        }
        updatePreview();
    }

    function restoreFields() {
        const initial = JSON.parse(getElement("editor-data").textContent);
        if (!initial) {
            return;
        }

        for (const [name, value] of Object.entries(initial)) {
            const input = editor.elements[name];
            if (!input) {
                continue;
            }

            if (input.type === "checkbox") {
                input.checked = value;
            } else {
                input.value = value;
            }
        }
    }

    async function uploadImage() {
        const uploadInput = getElement("image-upload");
        const saveButton = getElement("save-catalog");
        const imageMessage = getElement("image-message");
        const file = uploadInput.files[0];

        if (!file) {
            return;
        }
        if (file.size > 2 * 1024 * 1024) {
            throw new Error("이미지는 2MB 이하의 파일을 선택해 주세요.");
        }

        imageMessage.textContent = "이미지를 업로드하는 중입니다...";
        saveButton.disabled = true;

        try {
            const result = await request("/admin/item-images", {
                method: "POST",
                headers: { "Content-Type": file.type || "application/octet-stream" },
                body: file,
            });

            editor.elements.icon.value = result.icon;
            await loadImages();
            imageMessage.textContent = `이미지를 저장했습니다. ${result.width} × ${result.height}px`;
        } catch (error) {
            imageMessage.textContent = "이미지를 업로드하지 못했습니다.";
            throw error;
        } finally {
            saveButton.disabled = false;
            uploadInput.value = "";
        }
    }

    async function saveCatalog() {
        const payload = Object.fromEntries(new FormData(editor));
        payload.start_price = Number(payload.start_price);
        payload.weight = Number(payload.weight);
        payload.fishable = editor.elements.fishable.checked;

        const path = editingId ? `/admin/item-catalogs/${editingId}` : "/admin/item-catalogs";
        await request(path, {
            method: editingId ? "PATCH" : "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload),
        });

        await navigate("/admin/catalogs?saved=1");
    }

    function onSubmit(event) {
        event.preventDefault();
        void run(saveCatalog, getElement("save-catalog"));
    }

    function onImageChange() {
        void run(uploadImage, getElement("image-upload"));
    }

    // 초기 값 복원과 이벤트 연결은 화면 진입 시 한 번만 수행한다.
    restoreFields();
    editor.addEventListener("input", updatePreview);
    editor.addEventListener("submit", onSubmit);
    getElement("image-upload").addEventListener("change", onImageChange);

    updatePreview();
    void run(loadImages);
}
