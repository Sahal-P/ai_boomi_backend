/**
 * Every 3D illustration that can be placed in the page via <SceneSlot>.
 * Plain data, so slots can live in Server Components.
 */
export type SceneSpec = { name: "ribbon" };

export type SceneName = SceneSpec["name"];
