using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Shared presentation helpers for building visuals entirely from Unity
    /// primitives. Contains no simulation/AI logic — pure rendering utilities.
    /// </summary>
    public static class PrimitiveUtils
    {
        public static Material ColoredMaterial(Color color)
        {
            var shader = Shader.Find("Standard");
            if (shader == null)
                shader = Shader.Find("Unlit/Color");
            if (shader == null)
                shader = Shader.Find("Diffuse");
            if (shader == null) return null;
            var mat = new Material(shader);
            if (mat != null)
                mat.color = color;
            return mat;
        }

        public static void DestroyObj(Object obj)
        {
            if (obj == null) return;
#if UNITY_EDITOR
            if (!Application.isPlaying)
            {
                Object.DestroyImmediate(obj);
                return;
            }
#endif
            Object.Destroy(obj);
        }

        /// <summary>
        /// Creates a primitive as a child, strips its collider (unless keepCollider),
        /// assigns a shared material and returns the GameObject.
        /// </summary>
        public static GameObject Part(PrimitiveType type, Transform parent, Vector3 localPos, Vector3 localScale, Color color, bool keepCollider = false)
        {
            var go = GameObject.CreatePrimitive(type);
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            go.transform.localScale = localScale;
            if (!keepCollider)
                DestroyObj(go.GetComponent<Collider>());
            var renderer = go.GetComponent<Renderer>();
            if (renderer != null)
                renderer.sharedMaterial = ColoredMaterial(color);
            return go;
        }

        /// <summary>
        /// A simplified cone (Unity has no cone primitive). Deterministic —
        /// builds the same mesh for the same parameters every call.
        /// </summary>
        public static Mesh ConeMesh(float radius, float height, int segments = 10)
        {
            var mesh = new Mesh();
            var vertices = new Vector3[segments + 2];
            var uvs = new Vector2[segments + 2];
            var triangles = new int[segments * 3 + segments * 3];

            vertices[0] = new Vector3(0f, height, 0f);
            uvs[0] = new Vector2(0.5f, 1f);
            for (int i = 0; i <= segments; i++)
            {
                float angle = i / (float)segments * Mathf.PI * 2f;
                float x = Mathf.Cos(angle) * radius;
                float z = Mathf.Sin(angle) * radius;
                vertices[i + 1] = new Vector3(x, 0f, z);
                uvs[i + 1] = new Vector2(x / radius * 0.5f + 0.5f, z / radius * 0.5f + 0.5f);
            }

            int t = 0;
            for (int i = 0; i < segments; i++)
            {
                triangles[t++] = 0;
                triangles[t++] = i + 2;
                triangles[t++] = i + 1;
            }
            int baseCenter = vertices.Length;
            System.Array.Resize(ref vertices, baseCenter + 1);
            System.Array.Resize(ref uvs, baseCenter + 1);
            System.Array.Resize(ref triangles, t + segments * 3);
            vertices[baseCenter] = new Vector3(0f, 0f, 0f);
            uvs[baseCenter] = new Vector2(0.5f, 0.5f);
            for (int i = 0; i < segments; i++)
            {
                triangles[t++] = baseCenter;
                triangles[t++] = i + 1;
                triangles[t++] = i + 2;
            }

            mesh.vertices = vertices;
            mesh.uv = uvs;
            mesh.triangles = triangles;
            mesh.RecalculateNormals();
            return mesh;
        }

        /// <summary>A cone primitive built from ConeMesh.</summary>
        public static GameObject Cone(Transform parent, Vector3 localPos, float radius, float height, Color color, bool keepCollider = false)
        {
            var go = new GameObject("Cone");
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPos;
            var filter = go.AddComponent<MeshFilter>();
            filter.sharedMesh = ConeMesh(radius, height);
            var renderer = go.AddComponent<MeshRenderer>();
            renderer.sharedMaterial = ColoredMaterial(color);
            if (keepCollider)
                go.AddComponent<MeshCollider>().sharedMesh = filter.sharedMesh;
            return go;
        }
    }
}