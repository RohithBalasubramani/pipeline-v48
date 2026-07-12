// registry/ids.ts — registeredCardIds (split F11, 2026-07-12).
import { COMPONENTS } from "../components";
import { COMPOSE } from "../compose";
import { SPECIAL } from "../special";
import { FILL } from "./fill-loader";

export const registeredCardIds = (): number[] =>
  Array.from(new Set(
    [...Object.keys(SPECIAL), ...Object.keys(COMPONENTS), ...Object.keys(COMPOSE), ...Object.keys(FILL)].map(Number),
  )).sort((a, b) => a - b);
