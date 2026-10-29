ACTIVITY_EXPRESSION = r"""
(() => {
  const out = { ok: false, error: null };
  const action = __DCGL_ACTION__;
  const appId = __DCGL_APP_ID__;
  const gameName = __DCGL_GAME_NAME__;
  try {
    const wc = window.webpackChunkdiscord_app;
    if (!wc) throw new Error("Discord's module registry is not reachable");
    let req;
    wc.push([[Symbol()], {}, (r) => {
      const current = Object.keys((req && req.c) || {}).length;
      const incoming = Object.keys((r && r.c) || {}).length;
      if (incoming > current) req = r;
    }]);
    wc.pop();
    const modules = Object.values((req && req.c) || {});

    const findProp = (test) => {
      for (const record of modules) {
        try {
          const exp = record && record.exports;
          if (!exp || typeof exp !== "object") continue;
          for (const key of Object.keys(exp)) {
            const prop = exp[key];
            try { if (prop && test(prop)) return prop; } catch (e) {}
          }
        } catch (e) {}
      }
      return null;
    };
    const byDisplayName = (name) => findProp((prop) => prop.__proto__ &&
      prop.__proto__.constructor && prop.__proto__.constructor.displayName === name);
    const findDispatcher = () => findProp((prop) => prop._subscriptions &&
      typeof prop.subscribe === "function" && typeof prop.dispatch === "function" &&
      prop.__proto__ && typeof prop.__proto__.flushWaitQueue === "function");

    let state = window.__dcglActivity;
    if (!state) state = window.__dcglActivity = { real: {}, games: [], active: false };

    if (action === "clear") {
      const store = state.store;
      const dispatcher = state.dispatcher || findDispatcher();
      const removed = state.games.slice();
      state.games = [];
      if (state.active && store) {
        for (const name of Object.keys(state.real)) store[name] = state.real[name];
        state.active = false;
        state.real = {};
        if (dispatcher) {
          dispatcher.dispatch({
            type: "RUNNING_GAMES_CHANGE",
            added: [],
            removed,
            games: typeof store.getRunningGames === "function" ? store.getRunningGames() : [],
          });
          dispatcher.dispatch({ type: "LOCAL_ACTIVITY_UPDATE", socketId: null, pid: 9999, activity: null });
        }
      }
      out.ok = true;
      return JSON.stringify(out);
    }

    const store = state.store || byDisplayName("RunningGameStore");
    if (!store) throw new Error("Discord's running-game store was not found");
    const dispatcher = state.dispatcher || findDispatcher();
    if (!dispatcher) throw new Error("Discord's dispatcher was not found");
    state.store = store;
    state.dispatcher = dispatcher;

    // Patch every view Discord uses. Quest eligibility and the profile read
    // different ones; overriding getRunningGames alone leaves a game that no
    // card or heartbeat ever sees.
    const METHODS = [
      "getRunningGames", "getGameForPID", "getVisibleGame",
      "getVisibleRunningGames", "getRunningDiscordApplicationIds", "getCandidateGames",
    ];
    if (!state.active) {
      for (const name of METHODS) {
        if (typeof store[name] === "function" && !state.real[name]) state.real[name] = store[name];
      }
    }
    const real = state.real;
    const pid = 40000 + ((Date.now() % 1000) * 4);
    const exeName = (String(gameName).replace(/[^A-Za-z0-9]+/g, "") || "game") + ".exe";
    const game = {
      id: appId,
      name: gameName,
      icon: null,
      pid: pid,
      pidPath: [pid],
      processName: gameName,
      start: Date.now(),
      exeName: exeName,
      exePath: "c:/program files/" + exeName.toLowerCase(),
      cmdLine: "C:\\Program Files\\" + exeName,
      executables: [{ os: "win32", name: exeName, is_launcher: false }],
      windowHandle: 0,
      fullscreenType: 0,
      overlay: true,
      sandboxed: false,
      hidden: false,
      isLauncher: false,
    };
    // One quest at a time, so one fake game at a time.
    state.games = [game];

    const S = store;
    S.getRunningGames = () => [...real.getRunningGames.call(S), ...state.games];
    if (real.getGameForPID) {
      S.getGameForPID = (candidate) =>
        state.games.find((entry) => entry.pid === candidate) || real.getGameForPID.call(S, candidate);
    }
    if (real.getVisibleGame) {
      S.getVisibleGame = () => state.games[0] || real.getVisibleGame.call(S);
    }
    if (real.getVisibleRunningGames) {
      S.getVisibleRunningGames = () => [...real.getVisibleRunningGames.call(S), ...state.games];
    }
    if (real.getCandidateGames) {
      S.getCandidateGames = () => [...real.getCandidateGames.call(S), ...state.games];
    }
    if (real.getRunningDiscordApplicationIds) {
      S.getRunningDiscordApplicationIds = () => {
        const ids = real.getRunningDiscordApplicationIds.call(S);
        const ours = state.games.map((entry) => String(entry.id));
        return ids instanceof Set ? new Set([...ids, ...ours]) : [...(ids || []), ...ours];
      };
    }
    state.active = true;

    dispatcher.dispatch({
      type: "RUNNING_GAMES_CHANGE",
      added: [game],
      removed: [],
      games: S.getRunningGames(),
    });
    dispatcher.dispatch({
      type: "LOCAL_ACTIVITY_UPDATE",
      socketId: null,
      pid: game.pid,
      activity: {
        application_id: game.id,
        name: game.name,
        type: 0,
        details: null,
        state: null,
        timestamps: { start: game.start },
        icon: game.icon,
        assets: null,
      },
    });
    out.ok = true;
    out.pid = game.pid;
    out.running = S.getRunningGames().map((entry) => String(entry.id));
    return JSON.stringify(out);
  } catch (error) {
    out.error = String((error && error.message) || error);
    return JSON.stringify(out);
  }
})()
"""

ACTIVITY_STATE_EXPRESSION = r"""
(() => {
  const wc = window.webpackChunkdiscord_app;
  if (!wc) return JSON.stringify({ ok: false, error: "Discord's module registry is not reachable" });
  let req;
  wc.push([[Symbol()], {}, (r) => {
    const current = Object.keys((req && req.c) || {}).length;
    const incoming = Object.keys((r && r.c) || {}).length;
    if (incoming > current) req = r;
  }]);
  wc.pop();
  const modules = Object.values((req && req.c) || {});
  const appId = __DCGL_APP_ID__;
  try {
    for (const record of modules) {
      const exp = record && record.exports;
      if (!exp || typeof exp !== "object") continue;
      for (const key of Object.keys(exp)) {
        const prop = exp[key];
        if (!prop || prop.__proto__?.constructor?.displayName !== "LocalActivityStore") continue;
        if (typeof prop.getActivities !== "function") continue;
        const shown = prop.getActivities().some(
          (entry) => String((entry && entry.application_id) || "") === appId,
        );
        return JSON.stringify({ ok: true, shown: shown });
      }
    }
    return JSON.stringify({ ok: true, shown: null });
  } catch (error) {
    return JSON.stringify({ ok: false, error: String((error && error.message) || error) });
  }
})()
"""
