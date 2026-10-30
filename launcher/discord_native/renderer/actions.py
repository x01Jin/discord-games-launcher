QUEST_API_EXPRESSION = r"""
(async () => {
  const op = __DCGL_OP__;
  const fail = (error, extra) => JSON.stringify(Object.assign({ ok: false, error: String(error) }, extra || {}));
  try {
    const wc = window.webpackChunkdiscord_app;
    if (!wc) return fail("Discord's module registry is not reachable");
    const req = wc.push([[Symbol()], {}, (r) => r]);
    wc.pop();
    const mods = (req && req.c) || {};

    const nameOf = (candidate) => {
      if (!candidate || (typeof candidate !== "object" && typeof candidate !== "function")) return null;
      try {
        if (typeof candidate.getName === "function") return candidate.getName();
      } catch (e) { }
      try {
        if (typeof candidate.displayName === "string") return candidate.displayName;
      } catch (e) { }
      return null;
    };

    let questStore = null;
    let api = null;
    for (const id in mods) {
      const record = mods[id];
      if (!record || !record.exports) continue;
      const exported = record.exports;
      for (const candidate of [exported, exported.default, exported.A, exported.Z]) {
        const name = nameOf(candidate);
        if (!questStore && (name === "QuestStore" || name === "QuestsStore")) questStore = candidate;
      }
      for (const key of Object.keys(exported)) {
        let value;
        try {
          value = exported[key];
          if (
            !api &&
            value &&
            typeof value.get === "function" &&
            typeof value.post === "function" &&
            typeof value.del === "function" &&
            !value._dispatcher
          ) {
            api = value;
          }
        } catch (e) { }
      }
    }
    if (!questStore) return fail("Discord's QuestStore was not found");
    if (!api) return fail("Discord's HTTP client was not found");

    const raw = questStore.quests;
    let list = [];
    if (raw) {
      if (typeof raw.values === "function") list = Array.from(raw.values());
      else if (Array.isArray(raw)) list = raw;
      else list = Object.values(raw);
    }
    const quest = list.find((q) => q && String(q.id) === String(op.questId)) || null;
    const sealed = quest ? (quest.trafficMetadataSealed ?? null) : null;

    const post = async (url, body) => {
      const response = await api.post({ url: url, body: body });
      return {
        ok: response ? response.ok !== false : false,
        status: response ? response.status ?? null : null,
        body: response ? response.body ?? null : null,
      };
    };

    let result;
    if (op.kind === "enroll") {
      result = await post("/quests/" + op.questId + "/enroll", {
        location: 11,
        is_targeted: false,
        metadata_sealed: null,
        traffic_metadata_sealed: sealed,
      });
    } else if (op.kind === "video") {
      result = await post("/quests/" + op.questId + "/video-progress", {
        timestamp: op.timestamp,
      });
    } else if (op.kind === "heartbeat") {
      result = await post("/quests/" + op.questId + "/heartbeat", {
        application_id: op.applicationId,
        terminal: Boolean(op.terminal),
        executable_path: op.executablePath,
      });
    } else if (op.kind === "claim") {
      result = await post("/quests/" + op.questId + "/claim-reward", {
        platform: 0,
        location: 11,
        is_targeted: false,
        metadata_sealed: null,
        traffic_metadata_sealed: sealed,
      });
      if (result.ok && quest) {
        try {
          const status = quest.userStatus || (quest.userStatus = {});
          if (!status.claimedAt) status.claimedAt = new Date().toISOString();
        } catch (e) { }
      }
    } else {
      return fail("Unknown quest operation");
    }

    const body = result.body || {};
    if (!result.ok) {
      return fail(body.message || "Discord refused the quest request", {
        status: result.status,
        code: body.code ?? null,
        captcha: Boolean(body.captcha_key || body.captcha_sitekey),
      });
    }
    const keys = body.progress && typeof body.progress === "object"
      ? Object.keys(body.progress)
      : [];
    let credited = null;
    let creditedKey = null;
    const wanted = op.taskKey ? String(op.taskKey) : null;
    if (wanted && keys.includes(wanted)) {
      const entry = body.progress[wanted];
      if (entry && typeof entry.value === "number") {
        credited = entry.value;
        creditedKey = wanted;
      }
    }
    if (credited === null) {
      for (const key of keys) {
        const entry = body.progress[key];
        if (entry && typeof entry.value === "number") {
          credited = credited === null ? entry.value : Math.max(credited, entry.value);
          creditedKey = key;
        }
      }
    }
    return JSON.stringify({
      ok: true,
      status: result.status,
      enrolled: Boolean(body.enrolled_at),
      completed: Boolean(body.completed_at),
      progress: body.progress ?? null,
      credited: credited,
      creditedKey: creditedKey,
    });
  } catch (error) {
    const body = (error && error.body) || {};
    return fail((body && body.message) || (error && error.message) || error, {
      status: (error && error.status) || null,
      code: body.code ?? null,
    });
  }
})()
"""

NAVIGATE_QUESTS_EXPRESSION = r"""
(() => {
  if (location.pathname === "/quest-home") {
    return JSON.stringify({ ok: true, already: true });
  }
  try {
    history.pushState({}, "", "/quest-home");
    window.dispatchEvent(new PopStateEvent("popstate", { state: {} }));
    return JSON.stringify({ ok: true });
  } catch (error) {
    return JSON.stringify({ ok: false, error: String((error && error.message) || error) });
  }
})()
"""

CLAIM_CLICK_EXPRESSION = r"""
(() => {
  const norm = (value) =>
    String(value || "").toLowerCase().replace(/[^a-z0-9]+/g, "");
  const names = __DCGL_QUEST_NAMES__;
  const questId = String(__DCGL_QUEST_ID__ || "");
  const wanted = (Array.isArray(names) ? names : []).map(norm).filter(Boolean);
  const CLAIM = /^claim(\s+reward)?$/i;

  const claimButtonsIn = (root) =>
    Array.from(root.querySelectorAll('button, [role="button"]')).filter(
      (element) => CLAIM.test((element.innerText || "").trim()),
    );

  const buttons = claimButtonsIn(document).filter((button) => !button.disabled);
  if (!buttons.length) {
    return JSON.stringify({ ok: false, reason: "no-button" });
  }

  const cardOf = (button) => {
    let node = button;
    for (let level = 0; level < 10 && node; level += 1) {
      node = node.parentElement;
      if (!node) break;
      if (claimButtonsIn(node).length > 1) return null;
      if (questId) {
        for (const attribute of ["data-quest-id", "data-list-item-id", "id"]) {
          const value = String(node.getAttribute(attribute) || "");
          if (value && (value === questId || value.endsWith(questId))) return node;
        }
      }
      const text = norm(node.innerText || "");
      if (wanted.some((name) => text.includes(name))) return node;
      if (text.length > 400) return null;
    }
    return null;
  };

  const matches = [];
  for (const button of buttons) {
    const card = cardOf(button);
    if (card) matches.push({ button: button, card: card });
  }
  if (!matches.length) {
    return JSON.stringify({ ok: false, reason: "no-match", buttons: buttons.length });
  }
  if (matches.length > 1) {
    return JSON.stringify({ ok: false, reason: "ambiguous", buttons: buttons.length });
  }
  matches[0].button.click();
  return JSON.stringify({
    ok: true,
    buttons: buttons.length,
    card: norm(matches[0].card.innerText || "").slice(0, 120),
  });
})()
"""
