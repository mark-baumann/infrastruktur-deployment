// Local patch: an error while claiming one queued heartbeat run (e.g.
// "Queued-message interrupt authority is unavailable") must not crash server
// startup. Mark that run as failed and continue with the others.
import { readFileSync, writeFileSync } from "node:fs";

const file = "/app/server/dist/services/heartbeat.js";
const needle = "const claimed = await claimQueuedRun(queuedRun, companyAgents);";
const src = readFileSync(file, "utf8");
if (src.split(needle).length !== 2) {
  console.error(`patch-claim-crash: expected exactly one occurrence of the claim call in ${file}`);
  process.exit(1);
}
const replacement = `let claimed;
                try {
                    claimed = await claimQueuedRun(queuedRun, companyAgents);
                }
                catch (err) {
                    logger.error({ err, runId: queuedRun.id }, "claimQueuedRun failed; marking queued run as failed (local patch)");
                    await db.update(heartbeatRuns).set({
                        status: "failed",
                        error: \`claim failed: \${err?.message ?? String(err)}\`,
                        errorCode: "claim_failed",
                        finishedAt: new Date(),
                        updatedAt: new Date(),
                    }).where(and(eq(heartbeatRuns.id, queuedRun.id), eq(heartbeatRuns.status, "queued")))
                        .catch((updateErr) => logger.error({ err: updateErr, runId: queuedRun.id }, "failed to mark unclaimable queued run as failed"));
                    continue;
                }`;
writeFileSync(file, src.replace(needle, replacement));
console.log("patch-claim-crash: applied");
