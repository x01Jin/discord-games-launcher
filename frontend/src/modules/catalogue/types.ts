import type { CatalogueGame } from "../../shared/api-client";

export type { CatalogueGame };

export interface CatalogueFilters {
  query: string;
  limit: number;
}
