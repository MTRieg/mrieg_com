/**
 * lobby_state.js
 * 
 * Shared mutable state for the lobby system.
 * Callbacks are initialized as no-ops and overwritten by lobby_interactions.js
 */

// Private state
let _gameId = null;
let _playerId = null;

// ============ COOKIE UTILITIES ============

/**
 * Set a session cookie (expires 48 hours from now)
 * @param {string} name - Cookie name
 * @param {string} value - Cookie value
 */
function setCookie(name, value) {
  const expiryDate = new Date();
  expiryDate.setTime(expiryDate.getTime() + (48 * 60 * 60 * 1000)); // 48 hours
  const expires = `expires=${expiryDate.toUTCString()}`;
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; ${expires}`;
}

/**
 * Get a cookie value by name
 * @param {string} name - Cookie name
 * @returns {string|null} Cookie value or null if not found
 */
function getCookie(name) {
  const nameEQ = name + "=";
  console.log("getCookie called for:", name);
  console.log("Looking for:", nameEQ);
  console.log("All cookies:", document.cookie);
  
  const cookies = document.cookie.split(';');
  console.log("Cookie count:", cookies.length);
  
  for (let cookie of cookies) {
    cookie = cookie.trim();
    console.log("Checking cookie:", JSON.stringify(cookie), "startsWith:", cookie.startsWith(nameEQ));
    if (cookie.startsWith(nameEQ)) {
      const value = decodeURIComponent(cookie.substring(nameEQ.length));
      console.log("Found match! Value:", value);
      return value;
    }
  }
  
  console.log("No match found for:", name);
  return null;
}

/**
 * Delete a cookie by name
 * @param {string} name - Cookie name
 */
function deleteCookie(name) {
  document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 UTC;`;
}

export default{
  // Game and player identifiers (getters and setters auto-update URL and cookies)
  get gameId() {
    return _gameId;
  },
  set gameId(newGameId) {
    _gameId = newGameId;
    setCookie('gameId', newGameId);
    this._updateUrl();
  },
  
  get playerId() {
    return _playerId;
  },
  set playerId(newPlayerId) {
    _playerId = newPlayerId;
    setCookie('playerId', newPlayerId);
    this._updateUrl();
  },
  
  playerName: null,
  creator: false,

  /**
   * Load session data from cookies on initialization
   */
  loadSession() {
    const savedGameId = getCookie('gameId');
    const savedPlayerId = getCookie('playerId');
    
    if (savedGameId) {
      _gameId = savedGameId;
    }
    if (savedPlayerId) {
      _playerId = savedPlayerId;
    }
  },

  /**
   * Clear all session cookies
   */
  clearSession() {
    deleteCookie('gameId');
    deleteCookie('playerId');
    _gameId = null;
    _playerId = null;
  },

  /**
   * Get a cookie value (public wrapper)
   * @param {string} name - Cookie name
   * @returns {string|null} Cookie value or null if not found
   */
  getCookie(name) {
    return getCookie(name);
  },

  /**
   * Set a cookie value (public wrapper)
   * @param {string} name - Cookie name
   * @param {string} value - Cookie value
   */
  setCookie(name, value) {
    setCookie(name, value);
  },

  /**
   * Update the URL bar with current gameId and playerId
   * @private
   */
  _updateUrl() {
    const params = new URLSearchParams();
    if (_gameId) params.set('game_id', _gameId);
    if (_playerId) params.set('player_id', _playerId);
    const queryString = params.toString();
    const newUrl = queryString ? `?${queryString}` : window.location.pathname;
    window.history.pushState(null, '', newUrl);
  },

  // Polling configuration
  pollingDelay: 5000,      // 5 seconds between player list updates
  maxPollingAttempts: 60,  // number of attempts to fetch player list on join

  // ============ CALLBACK STUBS ============
  // These are overwritten by lobby_interactions.js

  /**
   * Called when Create Game/Player button is clicked.
   * Implementation should: validate input, fetch /games/api/create_game,
   * update state, and call UI functions to advance the status
   */
  onCreateBtnClick: () => {
    console.warn("onCreateBtnClick not implemented");
  },

  /**
   * Called when Join Game/Player button is clicked.
   * Implementation should: validate input, prompt for game ID if needed,
   * fetch /games/api/join_game, update state, and call UI functions
   */
  onJoinBtnClick: () => {
    console.warn("onJoinBtnClick not implemented");
  },

  /**
   * Called when a player name in the player list is clicked.
   * Implementation should: delete player if current user is creator,
   * fetch /games/api/leave_game, and update UI
   * 
   * @param {string} playerId - The ID of the player to interact with
   */
  onPlayerClick: (playerId) => {
    console.warn("onPlayerClick not implemented", playerId);
  },

  /**
   * Called when the Start Game button is clicked.
   * Implementation should: fetch /games/api/start_or_run_game,
   * handle response, and update UI (or reload)
   */
  onStartGameClick: () => {
    console.warn("onStartGameClick not implemented");
  },

  /**
   * Called when the invite link is clicked.
   * Implementation should: copy link to clipboard and show feedback
   */
  onInviteLinkClick: () => {
    console.warn("onInviteLinkClick not implemented");
  },
};