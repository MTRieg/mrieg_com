// --- ui_menu.js ---
// Collapsible menu for Knockout Game — starts closed on all devices

(function createPrototypeMenu() {
  // --- Create main menu container ---
  const menu = document.createElement("div");
  menu.id = "sideMenu";
  menu.classList.add("collapsed"); // menu starts closed
  document.body.appendChild(menu);

  // --- Create toggle button inside menu ---
  const toggle = document.createElement("button");
  toggle.id = "menuToggle";
  toggle.textContent = "☰";
  menu.appendChild(toggle);

  toggle.addEventListener("click", () => {
    menu.classList.toggle("expanded");
    menu.classList.toggle("collapsed");
  });

  // --- Create tab navigation bar ---
  const tabBar = document.createElement("div");
  tabBar.className = "tabBar";
  menu.appendChild(tabBar);

  const tabs = [
    { id: "controls", label: "Buttons" },
    { id: "leaderboard", label: "Leaderboard" },
    { id: "settings", label: "Settings" },
  ];

  tabs.forEach((tab, index) => {
    const btn = document.createElement("button");
    btn.className = "tabButton" + (index === 0 ? " active" : "");
    btn.dataset.tab = tab.id;
    btn.textContent = tab.label;
    tabBar.appendChild(btn);
  });

  // --- Create tab content container ---
  const contentContainer = document.createElement("div");
  contentContainer.id = "tabContent";
  menu.appendChild(contentContainer);

  tabs.forEach((tab, index) => {
    const content = document.createElement("div");
    content.id = tab.id + "Tab";
    content.className = "tabContent" + (index === 0 ? " active" : "");
    contentContainer.appendChild(content);
  });

  // --- Import other modules ---
  import("/static/ui_buttons.js").then(module => {
    if (typeof module.createButtonPanel === "function") {
      module.createButtonPanel(document.getElementById("controlsTab"));
    }
  });

  import("/static/ui_leaderboard.js").then(module => {
    if (typeof module.renderLeaderboard === "function") {
      module.renderLeaderboard(document.getElementById("leaderboardTab"));
    }
  });

  // --- Tab switching behavior ---
  const tabButtons = tabBar.querySelectorAll(".tabButton");
  const tabContents = contentContainer.querySelectorAll(".tabContent");

  tabButtons.forEach(btn => {
    btn.addEventListener("click", () => {
      tabButtons.forEach(b => b.classList.remove("active"));
      tabContents.forEach(c => c.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(btn.dataset.tab + "Tab").classList.add("active");
    });
  });

  // --- Inject styles ---
  const style = document.createElement("style");
  style.textContent = `
    /* --- Menu container --- */
    #sideMenu {
      position: fixed;
      left: 0;
      top: 0;
      width: 280px;
      height: 100%;
      background: #1b1b1b;
      color: #eee;
      display: flex;
      flex-direction: column;
      font-family: system-ui, sans-serif;
      z-index: 1000;
      box-shadow: 2px 0 8px rgba(0,0,0,0.5);
      transition: transform 0.3s ease;
    }

    /* --- Collapsed / expanded --- */
    #sideMenu.collapsed {
      transform: translateX(-280px); /* hidden */
    }
    #sideMenu.expanded {
      transform: translateX(0); /* shown */
    }

    /* --- Toggle button --- */
    #menuToggle {
      position: absolute;
      top: 10px;
      right: -40px; /* sticks out of menu */
      width: 40px;
      height: 40px;
      background: #333;
      color: #eee;
      border: none;
      font-size: 18px;
      cursor: pointer;
      border-radius: 0 5px 5px 0;
      transition: background 0.2s;
      z-index: 1001;
    }
    #menuToggle:hover {
      background: #444;
    }

    /* --- Tabs --- */
    .tabBar {
      display: flex;
    }
    .tabButton {
      flex: 1;
      background: #222;
      border: none;
      color: #ccc;
      padding: 10px;
      cursor: pointer;
      transition: background 0.2s, color 0.2s;
    }
    .tabButton:hover {
      background: #2a2a2a;
      color: #fff;
    }
    .tabButton.active {
      background: #333;
      border-bottom: 2px solid #0af;
      color: #fff;
    }

    .tabContent {
      display: none;
      padding: 10px;
      overflow-y: auto;
      font-size: 14px;
      flex: 1;
    }
    .tabContent.active {
      display: block;
    }

    /* --- General buttons/inputs --- */
    button, input, select {
      background: #333;
      color: #eee;
      border: 1px solid #444;
      border-radius: 4px;
      padding: 6px 8px;
    }
    button:hover {
      background: #444;
    }
  `;
  document.head.appendChild(style);
})();

