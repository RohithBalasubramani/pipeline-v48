/**
 * SHARED (misc concern) — panel-overview-harmonics-pq.
 *
 * The inert callback handed to every card's selection/nav handlers that this
 * fill deliberately does not wire (intra-window bucket nav, tile/feeder-row
 * selection). Only the date control on card 23 is live.
 */
export const noop = () => undefined;
