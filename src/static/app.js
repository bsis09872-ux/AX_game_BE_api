import { createPageNavigation } from "./navigation/page-navigation.js";
import { initializePage } from "./pages.js";

const navigation = createPageNavigation(initializePage);
navigation.start();
