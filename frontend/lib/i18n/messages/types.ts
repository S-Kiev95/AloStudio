/** Same keys as the Spanish source, any text: what every language fills in. */
export type Strings<T> = {
  [K in keyof T]: T[K] extends string ? string : Strings<T[K]>;
};
