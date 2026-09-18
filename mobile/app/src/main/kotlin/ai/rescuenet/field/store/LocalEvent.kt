package ai.rescuenet.field.store

import androidx.room.ColumnInfo
import androidx.room.Entity
import androidx.room.Index

/**
 * The device's local event log row — **`08` §12.2, DM-54**.
 *
 * DM-54 is authoritative for this shape and forces every part of it:
 *
 *  * the **same 15 canonical fields** of `08` §1.1 — no more, no fewer;
 *  * `priority` and `mac` are **absent** (DM-02, DM-03);
 *  * `serverSeq`, `tSrv` and `receivedVia` are **server-set** (`08` §1.3
 *    column B) and are therefore **nullable** on a locally authored,
 *    not-yet-acknowledged row. They are populated when the event is
 *    acknowledged or otherwise receives its server-side values;
 *  * received events carry all three on arrival;
 *  * the other 12 fields are **non-null on every row**.
 *
 * This is one append-only log holding both authored and received events
 * (`06` §5.1, `08` Part 12). No field is ever mutable except the three
 * server-set ones, which transition exactly once from null to their assigned
 * value — that is the acknowledgement described in Part 12, not a revision of a
 * device-authored fact (DM-37).
 *
 * Identity is `(deviceId, seq)` and nothing else — no UUID, no hash, no content
 * digest (D-05, DM-06).
 */
@Entity(
    tableName = "event",
    primaryKeys = ["device_id", "seq"],
    indices = [
        Index("server_seq"),
        Index(value = ["incident_id", "server_seq"]),
        Index(value = ["entity_type", "entity_id", "server_seq"]),
        Index(value = ["team_id", "server_seq"]),
    ],
)
data class LocalEvent(
    // ---- device-set: all twelve are non-null on every row (08 §1.3 column A)
    @ColumnInfo(name = "device_id") val deviceId: Int,
    @ColumnInfo(name = "seq") val seq: Long,
    @ColumnInfo(name = "type") val type: Int,
    @ColumnInfo(name = "entity_type") val entityType: Int,
    @ColumnInfo(name = "entity_id") val entityId: Long,
    @ColumnInfo(name = "payload") val payload: String,
    @ColumnInfo(name = "t_dev") val tDev: Long,
    @ColumnInfo(name = "schema_version") val schemaVersion: Int,
    @ColumnInfo(name = "responder_id") val responderId: Int,
    @ColumnInfo(name = "team_id") val teamId: Int,
    @ColumnInfo(name = "agency_id") val agencyId: Int,
    @ColumnInfo(name = "incident_id") val incidentId: Int,

    // ---- server-set: nullable until acknowledged (08 §1.3 column B, DM-54)
    @ColumnInfo(name = "server_seq") val serverSeq: Long? = null,
    @ColumnInfo(name = "t_srv") val tSrv: Long? = null,
    @ColumnInfo(name = "received_via") val receivedVia: Int? = null,
)
