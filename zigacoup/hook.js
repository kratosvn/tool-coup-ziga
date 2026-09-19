// Phase A hook script — inject vào trang zigavn.com SAU khi đã load xong (không dùng
// addInitScript vì các class BkXxx chỉ tồn tại sau khi gamelogic.min.js chạy xong).
// Xem docs/FINDINGS.md để biết vì sao chọn các điểm hook này và mức độ tin cậy.
//
// Idempotent: gọi lại nhiều lần không patch chồng.
(function () {
    if (window.__zigaBot) return window.__zigaBot;

    var bot = {
        version: 1,
        events: [],
        maxEvents: 2000,
        patchedClasses: [],
        ready: false,
    };

    function emit(kind, payload) {
        var rec = { kind: kind, t: Date.now(), payload: payload };
        bot.events.push(rec);
        if (bot.events.length > bot.maxEvents) bot.events.shift();
        try {
            console.log("__ZIGABOT__" + JSON.stringify(rec));
        } catch (e) {
            console.log("__ZIGABOT__" + JSON.stringify({ kind: "emit_error", t: Date.now(), payload: String(e) }));
        }
    }

    function patchDispatch(cls, label) {
        if (!cls || !cls.prototype || typeof cls.prototype.$g !== "function") return false;
        if (cls.prototype.__zigaPatched) return true;
        var orig = cls.prototype.$g;
        cls.prototype.$g = function (a) {
            try {
                emit("network_event", { cls: label, type: a && a.Type });
            } catch (e) {}
            return orig.apply(this, arguments);
        };
        cls.prototype.__zigaPatched = true;
        bot.patchedClasses.push(label);
        return true;
    }

    function tryPatchAll() {
        var targets = [
            ["BkBaseLogic", window.BkBaseLogic],
            ["BkCommonLogic", window.BkCommonLogic],
            ["BkInGameLogic", window.BkInGameLogic],
            ["BkChessInGameLogic", window.BkChessInGameLogic],
            ["BkCoUpInGameLogic", window.BkCoUpInGameLogic],
        ];
        var allDone = true;
        for (var i = 0; i < targets.length; i++) {
            if (!patchDispatch(targets[i][1], targets[i][0])) allDone = false;
        }
        return allDone;
    }

    var pollHandle = setInterval(function () {
        if (tryPatchAll()) {
            clearInterval(pollHandle);
            bot.ready = true;
            emit("bot_ready", { patched: bot.patchedClasses });
        }
    }, 250);
    // an toàn: đừng poll mãi mãi nếu trang không bao giờ load xong class
    setTimeout(function () {
        clearInterval(pollHandle);
        if (!bot.ready) emit("bot_ready_timeout", { patched: bot.patchedClasses });
    }, 60000);

    // ---------------- read API ----------------

    bot.isLoggedIn = function () {
        return !!(window.cc && cc.username && cc.username.length > 0);
    };

    bot.getScene = function () {
        return window.BkGlobal && window.BkGlobal.Yj;
    };

    bot.getGameLayer = function () {
        var scene = bot.getScene();
        return scene && typeof scene.ja === "function" ? scene.ja() : null;
    };

    bot.getActiveLogic = function () {
        return window.BkLogicManager && typeof BkLogicManager.na === "function" ? BkLogicManager.na() : null;
    };

    bot.isInCoUpGame = function () {
        var logic = bot.getActiveLogic();
        return !!(logic && window.BkCoUpInGameLogic && logic instanceof window.BkCoUpInGameLogic);
    };

    // Dump thô 1 quân để đối chiếu bằng mắt với UI thật (xác nhận tên field trong FINDINGS.md).
    bot.dumpPiece = function (idx) {
        var layer = bot.getGameLayer();
        if (!layer || !layer.V || !layer.V[idx]) return null;
        var p = layer.V[idx];
        var out = {};
        for (var k in p) {
            var v;
            try {
                v = p[k];
            } catch (e) {
                continue;
            }
            if (typeof v !== "function" && (v === null || typeof v !== "object")) out[k] = v;
        }
        return out;
    };

    bot.getBoard = function () {
        var layer = bot.getGameLayer();
        if (!layer || !layer.V) return null;
        var pieces = [];
        for (var i = 0; i < layer.V.length; i++) {
            var p = layer.V[i];
            if (!p) continue;
            pieces.push({
                idx: i,
                col: p.fa,
                row: p.rowIndex,
                owner: p.ka,
                type: p.Ga,
                removed: !!p.pa,
            });
        }
        var logic = bot.getActiveLogic();
        return {
            pieces: pieces,
            flipped: !!layer.hc,
            selected: layer.le,
            turnPlayerIndex: layer.Nj,
            myPlayerIndex: layer.Yc,
            gameState: logic ? logic.Fb : null,
        };
    };

    bot.getChessTypeEnum = function () {
        if (!window.BkChessType) return null;
        var out = {};
        for (var k in window.BkChessType) {
            var v = window.BkChessType[k];
            if (v && typeof v === "object" && "id" in v) out[k] = v.id;
        }
        return out;
    };

    // Chọn quân idx -> populate layer.tc[]/layer.Vp[] với các ô hợp lệ (đúng thông tin
    // 1 người chơi thật nhìn thấy khi bôi sáng). Gọi xong nên đợi 1 nhịp rồi mới
    // getHighlightedMoves() phòng trường hợp có round-trip mạng (xem FINDINGS.md mục "cần xác nhận").
    bot.selectPiece = function (idx) {
        var layer = bot.getGameLayer();
        if (!layer) return false;
        if (typeof layer.fp === "function") layer.fp();
        layer.QR(idx);
        return true;
    };

    bot.deselect = function () {
        var layer = bot.getGameLayer();
        if (!layer) return false;
        if (typeof layer.fp === "function") layer.fp();
        return true;
    };

    bot.getHighlightedMoves = function () {
        var layer = bot.getGameLayer();
        if (!layer) return null;
        var moves = [];
        (layer.tc || []).forEach(function (s) {
            if (s && s.x > 0) moves.push({ col: s.cq, row: s.Ir, kind: "tc" });
        });
        (layer.Vp || []).forEach(function (m) {
            if (m) moves.push({ col: m[0], row: m[1], kind: "vp" });
        });
        return moves;
    };

    // ---------------- write API ----------------

    // fromCol/fromRow/toCol/toRow: toạ độ LOCAL (cùng hệ với layer.V[].fa/.rowIndex,
    // tức là đã tính theo hướng hiển thị hiện tại). Hàm này tự áp dụng lật toạ độ
    // giống hệt client khi layer.hc = true trước khi gửi.
    bot.sendMove = function (fromCol, fromRow, toCol, toRow) {
        var layer = bot.getGameLayer();
        if (!layer) return false;
        var e = fromCol,
            g = fromRow,
            f = toCol,
            h = toRow;
        if (layer.hc) {
            g = 9 - g;
            h = 9 - h;
            e = 8 - e;
            f = 8 - f;
        }
        layer.T().PP(e, g, f, h);
        emit("action_sent", { fn: "PP", fromCol: fromCol, fromRow: fromRow, toCol: toCol, toRow: toRow, flipped: !!layer.hc });
        return true;
    };

    bot.sendChessAction = function (action) {
        var layer = bot.getGameLayer();
        if (!layer) return false;
        layer.T().yr(action);
        emit("action_sent", { fn: "yr", action: action });
        return true;
    };

    bot.sendReady = function (ready) {
        var layer = bot.getGameLayer();
        if (!layer) return false;
        layer.T().TC(!!ready);
        emit("action_sent", { fn: "TC", ready: !!ready });
        return true;
    };

    window.__zigaBot = bot;
    emit("hook_loaded", {});
    return bot;
})();
