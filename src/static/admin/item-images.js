function iconUrl(icon) {
    return /^[a-z0-9_]{1,50}$/.test(icon) ? `/static/sprites/item_${icon}.png` : null;
}
export function setImage(image, icon) {
    const url = iconUrl(icon);
    image.hidden = !url;
    const fallback = image.parentElement.querySelector(".image-fallback");
    if (fallback) fallback.hidden = Boolean(url);
    image.onload = () => {
        image.hidden = false;
        if (fallback) fallback.hidden = true;
    };
    image.onerror = () => {
        image.hidden = true;
        if (fallback) fallback.hidden = false;
    };
    if (url) image.src = url;
    else image.removeAttribute("src");
}
