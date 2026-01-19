/**
 * lobby_interactions.js
 * 
 * Handles all business logic and user interactions for the lobby.
 * Implements callbacks referenced in lobby_state.js
 * Calls UI functions from lobby_minimal.js
 */

import state from './lobby_state.js';
import * as minimal from './lobby_minimal.js';

// ============ INITIALIZATION ============

/**
 * Called by lobby_top.js on page load.
 * Checks URL parameters and initializes the lobby state/UI accordingly.
 */
export async function initialize() {
  const urlParams = new URLSearchParams(window.location.search);
  const existingGameId = urlParams.get('game_id');
  const extistingPlayerId = urlParams.get('player_id');
  const existingGamePassword = urlParams.get('game_password');


  console.log(existingGameId, existingGamePassword);


  // ============ Done: HANDLE URL ARGUMENTS ============
  // Implement logic here based on what URL params exist:
  // 
  // If game_id exists, check if existingGamePassword exists, ping server to view that game
  // If game_id but no game_password, check your cookies for a session token for that game and try pinging it like that
  // If game_id exists but you did not have valid credentials, set state to g and autofill the game_id
  // If game_id does not exist, set state to g and do nothing else
  // If game_id exists and you have valid game credentials, continue:
  // 
  // If you made it here, check cookies for player_id, find the corresponding session token, and validate it with the server
  // anywhere below, include i only if there are existing players in the game
  // If it exists, autofill player_id, and set status to pv/pvi depending on whether there are existing players
  // in any other scenario, set status to p/pi, and don't autofill player_id


  
  // If no game_id in URL, start at game selection screen
  if (!existingGameId) {
    minimal.statusControl.status = 'g';
    console.log('Initialize: No game_id in URL, setting status to "g"');
    return;
  }

  // Game ID exists, attempt to validate it
  console.log('Initialize: Found game_id in URL:', existingGameId);

  // Try to validate game with provided password or session token
  let gameValidated = false;
  let gameData = null;

  // Attempt 1: Check cookies for session token
  const sessionToken = state.getCookie(`game:${existingGameId}`);

    if (sessionToken) {
      console.log('Attempting to validate with session token from cookies');
      gameData = await fetchGameState(existingGameId);
      console.log('Fetched game data:', gameData);
      if (gameData) { // if the fetch was successful, we assume the session token is valid
        console.log('Session token valid for game:', existingGameId);
        gameValidated = true;
      }
    }


  // Attempt 2: Use provided password if it exists
  if (!gameValidated) {
    if (existingGamePassword) {
      if(requestSessionToken(`game:${existingGameId}`, existingGamePassword)){
        console.log('Attempting to validate with provided game password');
        gameData = await fetchGameState(existingGameId);
        if (gameData) { // if the fetch was successful, we assume the session token is valid
          gameValidated = true;
        }
      }
    }
  }

  

  

  // If game validation failed, set status to 'g' and autofill game_id
  if (!gameValidated) {
    console.log('Initialize: Game validation failed, setting status to "g" with autofilled game_id');
    minimal.statusControl.status = 'g';
    minimal.setInputs(existingGameId, null);
    return;
  }

  //I would add a check here for if the game has started, but that is handled in the backend now

  // Game validation succeeded, update state
  state.gameId = existingGameId;
  console.log(gameData.players.length);
  const hasPlayers = gameData && gameData.players && Object.keys(gameData.players).length > 0;
  const playerId = extistingPlayerId || state.getCookie('playerId');

  // Build status: 'p' (no player), 'pv' (player exists, but has not joined this game), or just i if player exists in this game
  let status = 'p';
  if (playerId) status += 'v'
  /*if (hasPlayers)*/ status += 'i'; // I changed my mind, show i regardless of player count
  console.log(playerId, gameData.players);
  if (playerId && gameData.players && playerId in gameData.players) {
    // Player exists in this game
    status = 'i'; // set status to just 'i'
  }
  
  if(playerId) {state.playerId = playerId;}
  minimal.statusControl.status = status;
  minimal.updateGameInfo(existingGameId, `mrieg.com/games/knockout?game_id=${existingGameId}`, gameData.state.next_turn_time);
  minimal.updatePlayerList(gameData.players, state.playerId);
  
}


// ============ URL VALIDATION HELPERS ============

/**
 * Fetch game state from server
 * @param {string} gameId
 * @returns {Promise<Object|null>}
 */
async function fetchGameState(gameId) {
  try {
    const res = await fetch(`/games/api/game_state?game_id=${encodeURIComponent(gameId)}`, {
      method: "GET",
      credentials: "same-origin",
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.error('Failed to fetch game state:', err);
  }
  return null;
}

async function requestSessionToken(gameId, password) {
  const res = await fetch("/games/api/create_session_cookie", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: gameId,
      game_password: password,
      player_id: null,
      player_password: null,
    })
  });
  if (res.ok) {
    console.log('Session cookie created successfully');
    return true;
  }else{
    console.warn('Failed to create session cookie');
    return false;
  }
}

// ============ CALLBACK IMPLEMENTATIONS ============

/**
 * Called when user clicks Create Game button.
 * TODO: Validate inputs, create game, advance to player setup
 */
state.onCreateBtnClick = async () => {
  console.log('onCreateBtnClick called');
  if(minimal.statusControl.status.includes('g')){
    const gameId = minimal.getInputs().name;
    const password = minimal.getInputs().password;
    await createGame(gameId, password);
  } else if(minimal.statusControl.status.includes('p')){
    const gameId = state.gameId;
    const username = minimal.getInputs().name;
    const password = minimal.getInputs().password;
    await registerWithExistingGame(gameId, username, password);
  }

};

/**
 * Called when user clicks Join Game button.
 * TODO: Prompt for game ID, join game, advance to player setup
 */
state.onJoinBtnClick = async () => {
  console.log('onJoinBtnClick called');
  if(minimal.statusControl.status.includes('g')){
    const gameId = minimal.getInputs().name;
    const password = minimal.getInputs().password;
    await viewExistingGame(gameId, password);
  } else if(minimal.statusControl.status.includes('p')){
    const gameId = state.gameId;
    const playerId = minimal.getInputs().name;
    const password = minimal.getInputs().password;
    await loginWithExistingGame(gameId, playerId, password);
  } else {
    console.warn('Join button clicked in unexpected state');
  }

};

/**
 * Called when user clicks a player name in the player list.
 * TODO: If current player is creator, delete the clicked player
 * 
 * @param {string} playerId - The ID of the player that was clicked
 */
state.onPlayerClick = async (playerId) => {
  console.log('onPlayerClick called with playerId:', playerId);
  // TODO: implement
  if (playerId === state.playerId){
    // TODO: allow player to create nickname
    console.log('Nickname creatiion not implemented yet');
  }else{
    if (state.creator){
      //delete the clicked player
      console.log('Deleting player (not implemented yet) with ID:', playerId);
    }
  }

};

/**
 * Called when user clicks Start Game button.
 * TODO: Send start_game request, update UI, reload if needed
 */
state.onStartGameClick = async () => {
  console.log('onStartGameClick called');
  if (minimal.statusControl.status.includes('i')){
    //if (state.creator){
      const res = await fetch("/games/api/start_game", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          game_id: state.gameId,
          player_id: state.playerId
        })
      });
      const data = await res.json();
      if (res.ok) {
        //reload the page to enter the game
        window.location.reload();
      } else {
        alert("Failed to start game. Note that only the game creator can start the game early.");
      }
    //}else{
      //console.warn('Start Game clicked by non-creator');
      //alert('Only the game creator can start the game early.');
    //}
  }else{
    console.warn('Start Game clicked when it should not be on screen');
  }
};

/**
 * Called when user clicks the invite link.
 * TODO: Copy to clipboard and show feedback
 */
state.onInviteLinkClick = async () => {
  console.log('onInviteLinkClick called');
  const inviteLink = minimal.ui.inviteLinkSpan.textContent;
  
  if (!inviteLink) {
    console.warn('No invite link to copy');
    return;
  }

  try {
    // Copy to clipboard using modern API
    await navigator.clipboard.writeText(inviteLink);
    
    // Show visual feedback - change text temporarily
    const originalText = minimal.ui.inviteLinkSpan.textContent;
    minimal.ui.inviteLinkSpan.textContent = 'Copied!';
    minimal.ui.inviteLinkSpan.style.color = '#4caf50';
    
    // Restore original text after 2 seconds
    setTimeout(() => {
      minimal.ui.inviteLinkSpan.textContent = originalText;
      minimal.ui.inviteLinkSpan.style.color = '#9ef';
    }, 2000);
  } catch (err) {
    console.error('Failed to copy to clipboard:', err);
    alert('Failed to copy link to clipboard');
  }
};

// ============ HELPER FUNCTIONS ============

/**
 * @param {string} gameId - The game ID to join
 */

//does not assume that a player name or id has been set yet
async function createGame(gameId, password) {
  console.log('createGame called with gameId:', gameId, 'password not logged for security');
  
  // gather advanced options from UI
  const adv = minimal.getAdvancedInputs();

  //ping the server to create the new game
  const res = await fetch("/games/api/create_game", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: gameId,
      password: password,
      start_delay: adv.startDelay,
      settings: {
        turn_interval: adv.timeLimit,
        max_players: adv.maxPlayers,
        board_size: adv.boardSize,
        board_shrink: adv.boardShrink,
      }
    })
  });
  const data = await res.json();
  if (res.ok) {
    //update state
    state.gameId = data.game_id;
    //change status to player setup plus show players
    minimal.statusControl.status = "pi";
  } else {
    alert("Failed to create game.");
    console.log(data);
  }
}


/**
 * Join an existing game with the given game ID.
 * First creates a session cookie, then fetches game state and updates UI.
 * 
 * @param {string} gameId - The game ID to join
 * @param {string} password - The game password
 */
async function viewExistingGame(gameId, password) {
  console.log('viewExistingGame called with gameId:', gameId);

  // Step 1: Create session cookie with game credentials
  const cookieRes = await fetch("/games/api/create_session_cookie", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: gameId,
      game_password: password,
      player_id: null,
      player_password: null,
    })
  });

  if (!cookieRes.ok) {
    alert("Failed to authenticate with game.");
    return;
  }

  // Step 2: Fetch game state using the session cookie
  const stateRes = await fetch(`/games/api/game_state?game_id=${encodeURIComponent(gameId)}`, {
    method: "GET",
    credentials: "same-origin",
  });

  const data = await stateRes.json();
  if (data.error) {
    alert("Failed to fetch game state.");
    return;
  }

  // Update state
  state.gameId = gameId;

  // Change status to player setup plus show players
  minimal.statusControl.status = "pi";
  minimal.updateGameInfo(gameId, `mrieg.com/games/knockout?game_id=${gameId}`, data.state.next_turn_time);
  minimal.updatePlayerList(data.players, state.playerId);
}



/**
 * Join an existing game with the given game ID.
 * Prompts for player name if needed, makes join request, updates UI.
 * 
 * @param {string} gameId - The game ID to join
 */
async function registerWithExistingGame(gameId, player_id, password) {
  console.log('registerWithExistingGame called with gameId:', gameId);


  //ping the server to join the game
  const res = await fetch("/games/api/register_for_game", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: gameId,
      player_id: player_id,
      password: password,
    })
  });
  const data = await res.json();
  if (res.ok) {
    //update state
    state.playerId = data.player_id;

    //change status to show players
    minimal.statusControl.status = "i";
    minimal.updateGameInfo(gameId, `mrieg.com/games/knockout?game_id=${gameId}`, data.state.next_turn_time)
    startPolling(gameId)


  } else {
    alert("Failed to join game.");
  }
}

async function loginWithExistingGame(gameId, username, password) {
  console.log('loginWithExistingGame called with gameId:', gameId);
  // TODO: implement

  // get cookie:
  const resCookie = await fetch("/games/api/create_session_cookie", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      player_id: username,
      player_password: password,
    })
  });
  if (!resCookie.ok) {
    alert("Failed to authenticate player.");
    return;
  }


  //ping the server to join the game
  const res = await fetch("/games/api/join_game", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: gameId,
      player_id: username
    })
  });
  const data = await res.json();
  if (res.ok || res.status === 409) {
    //update state
    state.playerId = data.player_id;

    //change status to show players
    minimal.statusControl.status = "i";
    minimal.updateGameInfo(gameId, `mrieg.com/games/knockout?game_id=${gameId}`, data.state.next_turn_time)
    startPolling(gameId)
  } else {
    alert("Failed to join game.");
  }
}

/**
 * Fetch player list from server and update UI.
 * Can be called multiple times (polling).
 * 
 * @param {number} repeatCount - Number of times to repeat the update
 */
async function loadPlayerList(repeatCount = 1, gameId) {
  console.log('updatePlayerList called with repeatCount:', repeatCount);

  let players = await loadPlayers(gameId);

  while (repeatCount > 0) {
    minimal.updatePlayerList(players, state.playerId);
    repeatCount -= 1;

    if (repeatCount > 0) {
      await new Promise(resolve =>
        setTimeout(resolve, state.pollingDelay)
      );
      players = await loadPlayers(gameId);
    }
  }
}


/**
 * Start polling for player list updates at regular intervals.
 * Uses state.pollingDelay and state.maxPollingAttempts.
 */
function startPolling(gameId) {
  console.log('startPolling started');
  loadPlayerList(state.maxPollingAttempts, gameId);
}


async function loadPlayers(gameId) {

  const res = await fetch(
    `/games/api/game_state?game_id=${encodeURIComponent(gameId)}`,
    {
      method: "GET",
      credentials: "same-origin", // ensure cookies are sent
    }
  );
  if (!res.ok) throw new Error(`HTTP ${res.status}`);

  const data = await res.json();
  if (data.error) {
    console.warn("Game state error:", data.error);
    return;
  }
  if (!data.players){
    console.warn("players not found, expect things to start breaking soon")
  }

  return(data.players || []);
}
