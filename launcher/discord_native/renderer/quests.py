QUESTS_EXPRESSION = r"""
(() => {
  const out = {
    ok: false,
    error: null,
    quests: [],
    questCount: 0,
    account: null,
    suspendedUntil: null,
    enrollmentBlockedUntil: null,
    storeFound: false,
    orbs: null
  };
  try {
    const wc = window.webpackChunkdiscord_app;
    if (!wc) throw new Error("Discord's module registry (webpackChunkdiscord_app) is not reachable");
    const req = wc.push([[Symbol()], {}, (r) => r]);
    wc.pop();
    const mods = (req && req.c) || {};

    const nameOf = (candidate) => {
      if (!candidate || (typeof candidate !== "object" && typeof candidate !== "function")) return null;
      try {
        if (typeof candidate.getName === "function") return candidate.getName();
      } catch (e) { /* stores are not all well behaved */ }
      try {
        if (typeof candidate.displayName === "string") return candidate.displayName;
      } catch (e) { /* ignore */ }
      return null;
    };

    let questStore = null;
    let userStore = null;
    let orbStore = null;
    for (const id in mods) {
      const record = mods[id];
      if (!record || !record.exports) continue;
      const exported = record.exports;
      const candidates = [exported, exported.default, exported.A, exported.Z];
      for (const candidate of candidates) {
        const name = nameOf(candidate);
        if (!name) continue;
        if (!questStore && (name === "QuestStore" || name === "QuestsStore")) questStore = candidate;
        else if (!userStore && name === "UserStore") userStore = candidate;
        else if (!orbStore && name === "VirtualCurrencyStore") orbStore = candidate;
      }
      if (questStore && userStore && orbStore) break;
    }

    if (!questStore) {
      // Duck-typed fallback for builds that rename the store.
      for (const id in mods) {
        const record = mods[id];
        if (!record || !record.exports) continue;
        for (const candidate of [record.exports, record.exports.default, record.exports.A]) {
          if (!candidate || typeof candidate !== "object") continue;
          try {
            if (candidate.quests && typeof candidate.getQuest === "function") { questStore = candidate; break; }
          } catch (e) { /* ignore */ }
        }
        if (questStore) break;
      }
    }

    if (!questStore) throw new Error("Discord's QuestStore was not found; the client may still be loading");
    out.storeFound = true;

    try {
      const user = typeof userStore?.getCurrentUser === "function" ? userStore.getCurrentUser() : null;
      if (user) out.account = { id: String(user.id || ""), username: user.username || null };
    } catch (e) { /* the account is decoration, not data */ }

    // The Orb pill on Discord's own quest page. Null until the client has
    // fetched it once this session (opening the quest page does that), which
    // the UI has to say rather than showing a wrong zero.
    try {
      if (orbStore && typeof orbStore.getCurrentBalance === "function") {
        const balance = orbStore.getCurrentBalance();
        if (typeof balance === "number" && Number.isInteger(balance) && balance >= 0) {
          out.orbs = balance;
        }
      }
    } catch (e) { /* the balance is decoration, not data */ }

    const future = (raw) => {
      if (!raw) return null;
      const when = new Date(raw);
      return Number.isNaN(when.getTime()) || when.getTime() <= Date.now() ? null : when.toISOString();
    };
    try { out.suspendedUntil = future(questStore.questAccessSuspendedUntil) || (questStore.isQuestAccessSuspended === true ? "suspended" : null); } catch (e) { /* ignore */ }
    try { out.enrollmentBlockedUntil = future(questStore.questEnrollmentBlockedUntil); } catch (e) { /* ignore */ }

    const raw = questStore.quests;
    let list = [];
    if (raw) {
      if (typeof raw.values === "function") list = Array.from(raw.values());
      else if (Array.isArray(raw)) list = raw;
      else list = Object.values(raw);
    }
    out.questCount = list.length;

    const entries = (tasks) => {
      if (!tasks) return [];
      if (typeof tasks.entries === "function" && typeof tasks.get === "function") return Array.from(tasks.entries());
      return Object.entries(tasks);
    };

    // Task keys this app can act on, best first. Play on desktop is something a
    // fake process can finish; a watch quest still has to be watched in the
    // client, but listing it is the difference between "no quests" and "here is
    // what you have".
    const ACTIONABLE = ["PLAY_ON_DESKTOP", "WATCH_VIDEO", "WATCH_VIDEO_ON_MOBILE"];
    const KIND = {
      PLAY_ON_DESKTOP: "play",
      WATCH_VIDEO: "watch",
      WATCH_VIDEO_ON_MOBILE: "watch_mobile"
    };

    for (const quest of list) {
      if (!quest || !quest.id) continue;
      const config = quest.config || {};
      const v2 = config.taskConfigV2 && config.taskConfigV2.tasks;
      const legacy = config.taskConfig && config.taskConfig.tasks;
      const v2Entries = entries(v2);
      const tasks = v2Entries.length ? v2Entries : entries(legacy);
      if (!tasks.length) continue;

      const byKey = {};
      for (const [key, task] of tasks) byKey[key] = task;

      let chosenKey = null;
      for (const key of ACTIONABLE) {
        if (byKey[key]) { chosenKey = key; break; }
      }
      if (!chosenKey) continue;
      const chosen = byKey[chosenKey];
      const kind = KIND[chosenKey];

      const applications = Array.isArray(chosen.applications) ? chosen.applications : [];
      const appId = applications.length && applications[0] && applications[0].id
        ? String(applications[0].id)
        : (config.application && config.application.id ? String(config.application.id) : null);

      const status = quest.userStatus || {};
      const progress = status.progress && status.progress[chosenKey];
      const assets = config.assets || {};
      const rewards = Array.isArray(config.rewardsConfig && config.rewardsConfig.rewards)
        ? config.rewardsConfig.rewards
        : [];
      // Every entry matters: a quest can list an in-game item first and Orbs
      // second, so reading rewards[0] reports no Orbs for a quest that pays
      // them. Discord's own card sums the entries the same way.
      let rewardOrbs = 0;
      let rewardPremiumOrbs = 0;
      let rewardAvatarDecoration = false;
      let rewardInGame = false;
      const rewardNames = [];
      for (const entry of rewards) {
        const base = Number(entry && entry.orbQuantity);
        if (base > 0) {
          rewardOrbs += base;
          const premium = Number(entry.premiumOrbQuantity);
          rewardPremiumOrbs += premium > 0 ? premium : base;
        }
        const rewardType = entry && entry.type;
        if (rewardType === 3) rewardAvatarDecoration = true;
        else if (rewardType === 1) rewardInGame = true;
        const label = entry && entry.messages && entry.messages.name;
        if (label) rewardNames.push(String(label));
      }
      const reward = rewards.length ? rewards[0] : null;
      const video = (chosen.assets && chosen.assets.video) || null;

      out.quests.push({
        id: String(quest.id),
        kind: kind,
        taskKey: chosenKey,
        name: (config.messages && config.messages.questName) || (config.messages && config.messages.gameTitle) || "Quest",
        gameName: (config.messages && config.messages.gameTitle) || (config.messages && config.messages.questName) || "Unknown game",
        publisher: (config.messages && config.messages.gamePublisher) || null,
        applicationId: appId,
        taskKeys: tasks.map((entry) => entry[0]),
        target: Number(chosen.target) || 0,
        progress: Number(progress && progress.value) || 0,
        enrolledAt: status.enrolledAt || null,
        completedAt: status.completedAt || null,
        claimedAt: status.claimedAt || null,
        dismissedAt: status.dismissedAt || null,
        expiresAt: config.expiresAt || null,
        startsAt: config.startsAt || null,
        tile: assets.gameTileLight || assets.gameTileDark || assets.gameTile || null,
        hero: assets.hero || null,
        logotype: assets.logotypeLight || assets.logotypeDark || null,
        video: video ? {
          url: video.url || null,
          thumbnail: video.thumbnail || null,
          width: Number(video.width) || null,
          height: Number(video.height) || null
        } : null,
        accent: (config.colors && config.colors.primary) || null,
        rewardType: reward ? reward.type : null,
        rewardName: rewardNames.length ? rewardNames[0] : null,
        rewardNames: rewardNames,
        rewardOrbs: rewardOrbs > 0 ? rewardOrbs : null,
        rewardPremiumOrbs: rewardOrbs > 0 ? rewardPremiumOrbs : null,
        rewardAvatarDecoration: rewardAvatarDecoration,
        rewardInGame: rewardInGame
      });
    }

    out.ok = true;
  } catch (error) {
    out.error = String((error && error.message) || error);
  }
  return JSON.stringify(out);
})()
"""
