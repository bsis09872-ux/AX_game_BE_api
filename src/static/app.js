import { createPageNavigation } from "./navigation/page-navigation.js";
import { initializePage, preparePage } from "./pages.js";

const navigation = createPageNavigation(initializePage, preparePage);
navigation.start();
