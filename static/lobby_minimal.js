/**
 * lobby_minimal.js
 * 
 * Handles lobby UI rendering and status management.
 * Does NOT contain business logic—just DOM manipulation.
 * Invokes state callbacks when user interacts with buttons.
 */

import state from './lobby_state.js';

// ============ CACHED DOM ELEMENTS ============
let ui = {};

export { ui };

/**
 * Cache all DOM element references.
 * Called once on initialization.
 */
export function initUI() {
  // Containers
  ui.lobby = document.getElementById('lobby');
  ui.setupSection = document.getElementById('setupSection');
  ui.infoSection = document.getElementById('infoSection');
  ui.gameBackground = document.getElementById('gameBackground');
  // Advanced options container (moved outside setupSection)
  ui.advancedSection = document.getElementById('advancedOptionsSection');

  // Inputs
  ui.nameInput = document.getElementById('name');
  ui.passwordInput = document.getElementById('password');

  // Display elements
  ui.gameIdSpan = document.getElementById('gameId');
  ui.inviteLinkSpan = document.getElementById('inviteLink');
  ui.playerListDiv = document.getElementById('playerList');
  ui.startInfo = document.getElementById('startInfo');

  // Buttons
  ui.createBtn = document.getElementById('createBtn');
  ui.joinBtn = document.getElementById('joinBtn');
  ui.startGameBtn = document.getElementById('startGameBtn');


  setStatus(_status); // Initialize visibility
}

// ============ STATUS MANAGEMENT ============
let _status = "g";
//status codes: g = game creation/join, p = player creation/join, i = in-game lobby, v = pre-validated input
let _nameChangeListener = null; // Track the name change listener

/**
 * Get current status.
 */
function getStatus() {
  return _status;
}

/**
 * Set status and update visibility accordingly.
 * 
 * @param {string} newStatus - valid status
 */
function setStatus(newStatus) {
  console.log(newStatus);
  // Validate
  if (!newStatus.includes('g') && !newStatus.includes('p') && !newStatus.includes('i')) {
    console.error(`Invalid status: ${newStatus}`);
    return;
  }
  if(newStatus.includes('g') && newStatus.includes('p')) {
    console.error(`Invalid status: cannot be both 'g' and 'p'`);
    return;
  }

  if(newStatus.includes('v') && !(newStatus.includes('g') || newStatus.includes('p'))){
    console.error( `status cannot be declared as validated unless you're in game_edit or player_edit mode`)
  }



  if (_status === 'i') {
    console.warn(
      'Should not change status after entering game (continuing anyway, but things may break)'
    );
  }

  _status = newStatus;

  setStatusDefaults();

  

  // Show appropriate section and update labels
  if (_status.includes('g')) {
    // Game creation/join mode
    ui.setupSection.style.display = 'block';
    if (ui.advancedSection) ui.advancedSection.style.display = 'block';
    ui.nameInput.placeholder = 'Enter Game Name';
    ui.passwordInput.placeholder = 'Enter Game Password';
    ui.createBtn.textContent = 'Create Game';
    ui.joinBtn.textContent = 'Join Existing Game';
  }
  if (_status.includes('p')) {
    // Player creation/join mode
    ui.setupSection.style.display = 'block';
    ui.nameInput.placeholder = 'Enter Player Username';
    ui.passwordInput.placeholder = 'Enter Player Password';
    ui.createBtn.textContent = 'Confirm new username';
    ui.joinBtn.textContent = 'Join with existing username';
  } 
  if (_status.includes('i')) {
    // In-game lobby mode
    ui.infoSection.style.display = 'block';
    if(!_status.includes('p')){
      ui.startGameBtn.style.display = 'inline-block';
    }
  }
  if (_status.includes('v')){
    // Handle pre-validated input
    ui.passwordInput.disabled = true;
    ui.passwordInput.value = '';
    ui.createBtn.disabled = true;
    ui.createBtn.style.opacity = '0.5';
    ui.createBtn.style.cursor = 'not-allowed';

    // Remove existing listener if any
    if (_nameChangeListener) {
      ui.nameInput.removeEventListener('input', _nameChangeListener);
    }

    // Add new listener for name changes
    _nameChangeListener = () => {
      onPrevalidatedNameChange();
    };
    ui.nameInput.addEventListener('input', _nameChangeListener);
  }
  clearInputs();
}

function setStatusDefaults() {
  // Hide both sections first
  ui.setupSection.style.display = 'none';
  ui.infoSection.style.display = 'none';
  // Ensure advanced options hidden by default
  ui.advancedSection.style.display = 'none';

  // Re-enable password field and create button for all non-validated states
  ui.passwordInput.disabled = false;
  ui.createBtn.disabled = false;
  ui.startGameBtn.style.display = 'none';
  ui.createBtn.style.opacity = '1';
  ui.createBtn.style.cursor = 'pointer';
}

/**
 * Handle name changes when input is pre-validated.
 * Removes 'v' flag from status and detaches the listener.
 */
function onPrevalidatedNameChange() {
  if (_nameChangeListener) {
    ui.nameInput.removeEventListener('input', _nameChangeListener);
    _nameChangeListener = null;
  }
  _status = _status.replace('v', '');
  setStatus(_status);
}

/**
 * Export object with getter/setter for status
 */
export const statusControl = {
  get status() {
    return getStatus();
  },
  set status(newStatus) {
    setStatus(newStatus);
  }
};

// ============ EVENT LISTENERS ============

/**
 * Attach click handlers to buttons.
 * Each handler invokes the corresponding state callback.
 * Called once on initialization.
 */
export function setupEventListeners() {
  // Create button
  ui.createBtn.addEventListener('click', () => {
    state.onCreateBtnClick();
  });

  // Join button
  ui.joinBtn.addEventListener('click', () => {
    state.onJoinBtnClick();
  });

  // Start game button
  ui.startGameBtn.addEventListener('click', () => {
    state.onStartGameClick();
  });

  // Invite link click to copy
  ui.inviteLinkSpan.addEventListener('click', () => {
    state.onInviteLinkClick();
  });
}




// ============ UI UPDATE FUNCTIONS ============

/**
 * Update the game info display (game ID, invite link, etc.)
 * Called by interactions after successfully joining/creating a game.
 * 
 * @param {string} gameId - The game ID to display
 * @param {string} inviteUrl - The invite URL to display
 * @param {string} startDeadline - Game start deadline ISO string
 */
export function updateGameInfo(gameId, inviteUrl, startDeadline) {
  console.log(gameId, inviteUrl, startDeadline);
  ui.gameIdSpan.textContent = gameId;
  ui.inviteLinkSpan.textContent = inviteUrl;
  
  ui.startInfo.textContent = `Game starts at: ${formatDeadline(startDeadline)}`;
}

function formatDeadline(startDeadline) {
  let formattedDeadline = 'soon';
  if (startDeadline) {
    try {
      const date = new Date(startDeadline);
      // Round to nearest minute: round up if seconds >= 30
      if (date.getSeconds() >= 30) {
        date.setMinutes(date.getMinutes() + 1);
      }
      date.setSeconds(0, 0);
      
      // Format: "Jan 10, 4:37 PM EST"
      formattedDeadline = date.toLocaleString('en-US', {
        month: 'short',
        day: 'numeric',
        hour: 'numeric',
        minute: '2-digit',
        hour12: true,
        timeZoneName: 'short'
      });
    } catch (e) {
      console.error('Failed to parse deadline:', e);
      formattedDeadline = startDeadline;
    }
  }
  return formattedDeadline;
}
/**
 * Update the player list display.
 * Called by interactions after fetching player list from server.
 * 
 * @param {Object|Array} players - Players data from server (object map or array)
 * @param {string} currentPlayerId - The current player's ID (to highlight/update input)
 */
export function updatePlayerList(players, currentPlayerId) {
  // Clear existing list
  console.log(players, currentPlayerId);

  ui.playerListDiv.innerHTML = '';

  // Normalize players into array of [id, playerData] pairs
  let playerArray = [];
  if (Array.isArray(players)) {
    playerArray = players.map((p, i) => [String(i), p]);
  } else if (typeof players === 'object' && players !== null) {
    playerArray = Object.entries(players);
  }

  if (playerArray.length > 0) {
    for (const [playerId, playerData] of playerArray) {
      const div = document.createElement('div');

      div.textContent = `- ${playerData.name || playerId}
                          ${(playerId === currentPlayerId || playerData.name == currentPlayerId) ? ' (you)' : ''}`;

      div.style.cursor = 'pointer';

      // Hover effect: strikethrough if current player is creator
      div.addEventListener('mouseover', () => {
        if (state.creator) {
          div.style.textDecoration = 'line-through';
        }
      });

      div.addEventListener('mouseout', () => {
        div.style.textDecoration = 'none';
      });

      // Click to delete (if creator)
      div.addEventListener('click', () => {
        state.onPlayerClick(playerId);
      });

      // Update local input if this is our player
      if (playerId === currentPlayerId) {
        ui.nameInput.value = playerData.name || '';
        state.playerName = playerData.name;
      }

      ui.playerListDiv.appendChild(div);
    }
  } else {
    ui.playerListDiv.textContent = '(No players yet)';
  }
}

/**
 * Get current input values (for use by interactions).
 * 
 * @returns {Object} Object with name and password values
 */
export function getInputs() {
  return {
    name: ui.nameInput.value.trim(),
    password: ui.passwordInput.value.trim(),
  };
}

/**
 * Return values from the advanced options panel.
 * Normalizes to numbers and applies sane defaults when fields are empty.
 * Converts time inputs from selected units (minutes/hours/days) to seconds.
 */
export function getAdvancedInputs() {
  const adv = {
    maxPlayers: 10,
    startDelay: 86400,
    timeLimit: 86400,
    boardSize: 800,
    boardShrink: 50,
  };

  if (!ui.advancedSection) return adv;

  // Unit conversion multipliers
  const unitMultipliers = {
    seconds: 1,
    minutes: 60,
    hours: 3600,
    days: 86400
  };

  // Helper to get active unit button value
  const getActiveUnit = (buttonGroupIndex) => {
    const groups = document.querySelectorAll('.unit-button-group');
    if (groups.length > buttonGroupIndex) {
      const activeBtn = groups[buttonGroupIndex].querySelector('.unit-button.active');
      return activeBtn?.dataset?.unit || 'days';
    }
    return 'days';
  };

  // Table-driven parsing for numeric fields without units
  const specs = [
    { id: 'maxPlayers', key: 'maxPlayers', min: 1 },
    { id: 'boardSize', key: 'boardSize', min: 1 },
    { id: 'boardShrink', key: 'boardShrink', min: null },
  ];

  for (const s of specs) {
    try {
      const el = document.getElementById(s.id);
      const v = parseInt(el?.value || '', 10);
      if (!Number.isNaN(v) && (s.min === null || v >= s.min)) {
        adv[s.key] = v;
      }
    } catch (e) {
      // ignore parse errors and keep default
    }
  }

  // Handle startDelay with unit conversion
  try {
    const startDelayEl = document.getElementById('startDelay');
    const startDelayUnit = getActiveUnit(0);
    const startDelayValue = parseInt(startDelayEl?.value || '', 10);
    
    // Use 1 as default if empty or invalid
    const finalValue = !Number.isNaN(startDelayValue) && startDelayValue >= 10 ? startDelayValue : 1;
    adv.startDelay = finalValue * (unitMultipliers[startDelayUnit] || 86400);
  } catch (e) {
    // ignore and keep default
  }

  // Handle timeLimit with unit conversion
  try {
    const timeLimitEl = document.getElementById('timeLimit');
    const timeLimitUnit = getActiveUnit(1);
    const timeLimitValue = parseInt(timeLimitEl?.value || '', 10);
    
    // Use 1 as default if empty or invalid
    const finalValue = !Number.isNaN(timeLimitValue) && timeLimitValue >= 1 ? timeLimitValue : 1;
    adv.timeLimit = finalValue * (unitMultipliers[timeLimitUnit] || 86400);
  } catch (e) {
    // ignore and keep default
  }

  return adv;
}

/**
 * Clear input fields (useful after game creation).
 */
export function clearInputs() {
  ui.nameInput.value = '';
  ui.passwordInput.value = '';
}

export function setInputs(name, password) {
  ui.nameInput.value = name || '';
  ui.passwordInput.value = password || '';
}
