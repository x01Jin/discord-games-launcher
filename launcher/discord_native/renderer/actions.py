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
      } catch (e) { /* stores are not all well behaved */ }
      try {
        if (typeof candidate.displayName === "string") return candidate.displayName;
      } catch (e) { /* ignore */ }
      return null;
    };

    // Same discovery as the quest reader: named stores first, because the
    // duck-typed matcher can land on an unrelated cache in this build.
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
        // Some modules export the global object, whose numeric keys are
        // cross-origin iframes. Reading a property off one throws, and that
        // error used to abort the whole scan before the HTTP client was found.
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
        } catch (e) { /* frames from another origin are not candidates */ }
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
      // Discord's own game client posts this every twenty seconds; the server
      // credits play time per beat, so nothing has to run on the machine.
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
    } else {
      return fail("Unknown quest operation");
    }

    const body = result.body || {};
    if (!result.ok) {
      return fail(body.message || "Discord refused the quest request", {
        status: result.status,
        code: body.code ?? null,
        // A claim that needs a challenge comes back with one of these keys.
        captcha: Boolean(body.captcha_key || body.captcha_sitekey),
      });
    }
    // One beat answers with the running total for the quest's task, which is
    // how the caller knows the target was reached without another full read.
    let credited = null;
    if (body.progress && typeof body.progress === "object") {
      for (const key of Object.keys(body.progress)) {
        const entry = body.progress[key];
        if (entry && typeof entry.value === "number") {
          credited = Math.max(credited === null ? 0 : credited, entry.value);
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
  const target = String(__DCGL_QUEST_NAME__).toLowerCase().replace(/[^a-z0-9]+/g, "");
  const buttons = Array.from(
    document.querySelectorAll('button, [role="button"]'),
  ).filter((element) => /^claim(\s+reward)?$/i.test((element.innerText || "").trim()));
  for (const button of buttons) {
    let node = button;
    let card = "";
    for (let level = 0; level < 8 && node; level += 1) {
      node = node.parentElement;
      if (!node) break;
      const text = String(node.innerText || "");
      if (text.length >= 60) {
        card = text;
        break;
      }
    }
    if (target && card.toLowerCase().replace(/[^a-z0-9]+/g, "").includes(target)) {
      button.click();
      return JSON.stringify({ ok: true, buttons: buttons.length });
    }
  }
  return JSON.stringify({ ok: false, reason: buttons.length ? "no-match" : "no-button" });
})()
"""
