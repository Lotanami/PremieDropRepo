(function () {
    "use strict";

    var fs = require("fs");
    var path = require("path");
    var os = require("os");
    var queuePath = path.join(
        process.env.APPDATA || path.join(os.homedir(), "AppData", "Roaming"),
        "PremieDrop",
        "premiedrop_import_queue.json"
    );
    var queue = null;
    var importing = false;
    var lastHandledQueue = "";

    var countLabel = document.getElementById("file-count");
    var importButton = document.getElementById("import");
    var refreshButton = document.getElementById("refresh");
    var message = document.getElementById("message");
    var folderName = document.getElementById("folder-name");

    function setMessage(text, kind) {
        message.textContent = text;
        message.className = "message" + (kind ? " " + kind : "");
    }

    function queueId(value) {
        return value && value.created_at ? value.created_at : "";
    }

    function refreshQueue(autoImport) {
        if (importing) {
            return;
        }
        queue = null;
        importButton.disabled = true;

        if (!fs.existsSync(queuePath)) {
            countLabel.textContent = "No queue found";
            folderName.textContent = "No PremieDrop folder selected";
            setMessage("Waiting for PremieDrop...");
            return;
        }

        try {
            queue = JSON.parse(fs.readFileSync(queuePath, "utf8"));
            folderName.textContent = queue.project_folder || "No PremieDrop folder selected";
            folderName.title = queue.project_folder || "";
            if (!queue.project_folder || !fs.existsSync(queue.project_folder)) {
                countLabel.textContent = "Folder unavailable";
                setMessage(
                    "Select a valid media folder in PremieDrop before importing.",
                    "error"
                );
                return;
            }
            if (!queue.files || !queue.files.length) {
                countLabel.textContent = "Queue is empty";
                setMessage(
                    queue.status === "stale"
                        ? "Project folder changed. Press Import All to Premiere again."
                        : "PremieDrop created a queue without importable files.",
                    "error"
                );
                return;
            }

            var missingFiles = queue.files.filter(function (entry) {
                return !entry.path || !fs.existsSync(entry.path);
            });
            if (missingFiles.length) {
                countLabel.textContent = missingFiles.length + " missing";
                setMessage(
                    "Queued files moved or were deleted. Press Import All to Premiere again.",
                    "error"
                );
                return;
            }

            countLabel.textContent =
                queue.files.length + (queue.files.length === 1 ? " file" : " files");

            if (queue.status === "completed") {
                importButton.disabled = false;
                setMessage("Last import completed. Press Import Now to import this queue again.", "success");
                return;
            }

            importButton.disabled = false;
            setMessage("PremieDrop import received.");
            if (
                autoImport &&
                queue.status === "pending" &&
                queueId(queue) !== lastHandledQueue
            ) {
                lastHandledQueue = queueId(queue);
                importQueue(false);
            }
        } catch (error) {
            countLabel.textContent = "Queue error";
            setMessage(error.message, "error");
        }
    }

    function markQueue(status, result) {
        if (!queue) {
            return;
        }
        queue.status = status;
        queue.completed_at = new Date().toISOString();
        queue.result = result;
        fs.writeFileSync(queuePath, JSON.stringify(queue, null, 2), "utf8");
    }

    function importQueue(forceImport) {
        if (importing || !queue || !queue.files || !queue.files.length) {
            return;
        }

        var missingFiles = queue.files.filter(function (entry) {
            return !entry.path || !fs.existsSync(entry.path);
        });
        if (missingFiles.length) {
            importButton.disabled = true;
            countLabel.textContent = missingFiles.length + " missing";
            setMessage(
                "Queued files are no longer on disk. Re-run Import All in PremieDrop.",
                "error"
            );
            return;
        }

        importing = true;
        importButton.disabled = true;
        refreshButton.disabled = true;
        setMessage("Importing into Premiere...");

        var payload = JSON.stringify(queue.files);
        var script =
            "PremieDropBridge.importFiles(" +
            JSON.stringify(payload) + "," +
            (forceImport ? "true" : "false") +
            ")";

        window.__adobe_cep__.evalScript(script, function (rawResult) {
            importing = false;
            refreshButton.disabled = false;
            try {
                var result = JSON.parse(rawResult);
                if (!result.ok) {
                    markQueue("failed", result);
                    setMessage(result.error || "Premiere rejected the import.", "error");
                    importButton.disabled = false;
                    return;
                }

                markQueue("completed", result);
                countLabel.textContent = result.imported + " imported";
                setMessage(
                    "Imported " + result.imported + " file" +
                    (result.imported === 1 ? "" : "s") +
                    (result.skipped ? "; " + result.skipped + " already present." : "."),
                    "success"
                );
            } catch (error) {
                setMessage("Unexpected response from Premiere: " + rawResult, "error");
                importButton.disabled = false;
            }
        });
    }

    refreshButton.addEventListener("click", function () {
        refreshQueue(false);
    });
    importButton.addEventListener("click", function () {
        importQueue(true);
    });
    refreshQueue(true);
    setInterval(function () {
        refreshQueue(true);
    }, 1000);
}());
