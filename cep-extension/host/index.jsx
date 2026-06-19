var PremieDropBridge = PremieDropBridge || {};

PremieDropBridge.escapeJson = function (value) {
    return String(value)
        .replace(/\\/g, "\\\\")
        .replace(/"/g, '\\"')
        .replace(/\r/g, "\\r")
        .replace(/\n/g, "\\n");
};

PremieDropBridge.result = function (ok, imported, skipped, error) {
    return '{"ok":' + (ok ? "true" : "false") +
        ',"imported":' + Number(imported || 0) +
        ',"skipped":' + Number(skipped || 0) +
        ',"error":"' + PremieDropBridge.escapeJson(error || "") + '"}';
};

PremieDropBridge.findOrCreateBin = function (name) {
    var root = app.project.rootItem;
    var i;
    var child;

    for (i = 0; i < root.children.numItems; i++) {
        child = root.children[i];
        if (child && child.name === name && child.type === ProjectItemType.BIN) {
            return child;
        }
    }

    return root.createBin(name);
};

PremieDropBridge.collectMediaPaths = function (item, paths) {
    var i;
    var child;
    var mediaPath;

    if (!item) {
        return;
    }

    if (item.type === ProjectItemType.CLIP) {
        try {
            mediaPath = item.getMediaPath();
            if (mediaPath) {
                paths[String(mediaPath).toLowerCase()] = true;
            }
        } catch (ignore) {}
    }

    if (item.children) {
        for (i = 0; i < item.children.numItems; i++) {
            child = item.children[i];
            PremieDropBridge.collectMediaPaths(child, paths);
        }
    }
};

PremieDropBridge.importFiles = function (filesJson, forceImport) {
    try {
        if (!app.project) {
            return PremieDropBridge.result(false, 0, 0, "No Premiere project is open.");
        }

        var files = JSON.parse(filesJson);
        var grouped = {};
        var existing = {};
        var section;
        var i;
        var imported = 0;
        var skipped = 0;

        PremieDropBridge.collectMediaPaths(app.project.rootItem, existing);

        for (i = 0; i < files.length; i++) {
            var normalizedPath = String(files[i].path).toLowerCase();
            if (!forceImport && existing[normalizedPath]) {
                skipped++;
                continue;
            }
            section = files[i].section || "PremieDrop";
            if (!grouped[section]) {
                grouped[section] = [];
            }
            grouped[section].push(files[i].path);
        }

        for (section in grouped) {
            if (grouped.hasOwnProperty(section)) {
                var targetBin = PremieDropBridge.findOrCreateBin(section);
                var paths = grouped[section];
                if (app.project.importFiles(paths, true, targetBin, false)) {
                    imported += paths.length;
                }
            }
        }

        return PremieDropBridge.result(true, imported, skipped, "");
    } catch (error) {
        return PremieDropBridge.result(false, 0, 0, error.toString());
    }
};
