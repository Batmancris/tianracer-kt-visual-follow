import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";

const root = path.resolve(import.meta.dirname, "..", "..");
const htmlPath = path.join(root, "tools", "bear_overlay_prod.html");
const source = fs.readFileSync(htmlPath, "utf8");

function expectIncludes(snippet, description) {
  assert.ok(source.includes(snippet), `Expected ${description}`);
}

function expectRegex(pattern, description) {
  assert.match(source, pattern, `Expected ${description}`);
}

expectIncludes('id="mjpeg-reconnect-reason"', "MJPEG reconnect reason field");
expectIncludes('id="mjpeg-reconnect-time"', "MJPEG reconnect time field");

for (const state of ["offline", "connecting", "live", "stale", "reconnecting", "error"]) {
  expectIncludes(`'${state}'`, `state token '${state}'`);
}

expectRegex(/function stopMjpegPreview\([^)]*\)/, "stopMjpegPreview(...)");
expectRegex(/function reconnectMjpegPreview\(reason\)/, "reconnectMjpegPreview(reason)");
expectRegex(/function mjpegWatchdogLoop\(\)/, "mjpegWatchdogLoop()");
expectRegex(/function startMjpegPreview\(\)/, "startMjpegPreview()");
expectRegex(/function stopSession\(\)/, "single disconnect/session stop entrypoint");

expectRegex(/latest_seq/, "status-based sequence tracking");
expectRegex(/last_frame_age_ms/, "status-based frame age tracking");
expectRegex(/client_count/, "client count exposed in status handling");
expectRegex(/lastReconnectReason/, "reconnect reason state");
expectRegex(/lastReconnectTime/, "reconnect time state");
expectRegex(/MIN_MJPEG_RECONNECT_INTERVAL_MS/, "reconnect throttling constant");
expectRegex(/MJPEG_NO_CLIENT_THRESHOLD/, "no-client reconnect threshold constant");
expectRegex(/mjpegNoClientCount/, "no-client reconnect state");
expectRegex(/reconnectMjpegPreview\('no mjpeg client'\)/, "reconnect when no mjpeg client is attached");
expectRegex(/tuningDirtyFields/, "tuning dirty field tracking");
expectRegex(/cameraDirtyFields/, "camera dirty field tracking");
expectRegex(/CAMERA_AUTO_APPLY_DELAY_MS/, "camera auto apply delay constant");
expectRegex(/scheduleCameraAutoApply\(\)/, "camera auto apply scheduler");
expectRegex(/cameraAutoApplyTimer/, "camera auto apply timer state");
expectRegex(/!cameraDirtyFields\.has\('brightness'\)/, "do not overwrite brightness while editing");
expectRegex(/!cameraDirtyFields\.has\('exposure'\)/, "do not overwrite exposure while editing");
expectRegex(/!tuningDirtyFields\.has\('max-speed'\)/, "do not overwrite max-speed while editing");
expectRegex(/!tuningDirtyFields\.has\('max-steering'\)/, "do not overwrite max-steering while editing");
expectRegex(/followTuningStatusTopic\.subscribe\(\(msg\) => \{[\s\S]*tuningDirtyFields\.clear\(\)/, "clear dirty tuning fields after successful follow tuning ack");
expectRegex(/cameraStatusTopic\.subscribe\(\(msg\) => \{[\s\S]*cameraDirtyFields\.clear\(\)/, "clear dirty camera fields after successful camera status ack");
expectRegex(/setTuningFieldValue\('brightness', payload\.current\.brightness\)/, "sync brightness from camera status");
expectRegex(/setTuningFieldValue\('exposure', payload\.current\.exposure\)/, "sync exposure from camera status");
expectIncludes('id="follow-scan-topic"', "follow scan topic field");
expectIncludes('id="follow-theta-raw"', "follow theta_raw field");
expectIncludes('id="follow-theta-filt"', "follow theta_filt field");
expectIncludes('id="follow-stop-distance"', "follow stop_distance field");
expectIncludes('id="follow-full-speed-distance"', "follow full_speed_distance field");
expectRegex(/id="max-speed-value">0\.50</, "default max_speed value 0.50");
expectRegex(/id="max-speed-number"[^>]*value="0\.50"/, "default max_speed input 0.50");
expectRegex(/id="max-speed-range"[^>]*value="0\.50"/, "default max_speed range 0.50");
expectRegex(/id="max-steering-number"[^>]*max="1\.00"/, "max steering input upper bound 1.00");
expectRegex(/id="max-steering-range"[^>]*max="1\.00"/, "max steering range upper bound 1.00");
expectRegex(/id="stop-distance-value">0\.50</, "default stop_distance value 0.50");
expectRegex(/id="full-speed-distance-value">1\.00</, "default full_speed_distance value 1.00");
expectRegex(/followScanTopic\.textContent = payload\.scan_topic \|\| '-'/, "render scan_topic from follow status");
expectRegex(/followThetaRaw\.textContent = formatNumber\(payload\.theta_raw, 3\)/, "render theta_raw from follow status");
expectRegex(/followThetaFilt\.textContent = formatNumber\(payload\.theta_filt, 3\)/, "render theta_filt from follow status");
expectRegex(/followStopDistance\.textContent = formatNumber\(payload\.stop_distance_m, 3\)/, "render stop_distance from follow status");
expectRegex(/followFullSpeedDistance\.textContent = formatNumber\(payload\.full_speed_distance_m, 3\)/, "render full_speed_distance from follow status");

console.log("bear_overlay MJPEG lifecycle checks passed");
