using UnityEngine;

namespace NpcAi.Client
{
    /// <summary>
    /// Third-person player character (visual/client-side only). Movement is
    /// purely local — the authoritative Python simulation is never told to move
    /// the player. Position is reported via TransportClient.SendPlayerUpdate so
    /// the Python layer can compute the nearest location / nearby targets.
    /// Contains no simulation, decision or AI logic.
    /// </summary>
    public class PlayerController : MonoBehaviour
    {
        public TransportClient transport;
        public float worldScale = 1f;
        public float moveSpeed = 6f;
        public float sprintSpeed = 10f;
        public float mouseSensitivity = 2f;
        public float cameraDistance = 6f;
        public float cameraHeight = 2.5f;
        public float updateInterval = 0.25f;
        public float minCameraDistance = 2f;
        public float maxCameraDistance = 14f;
        public float zoomSpeed = 2f;
        public float cameraFollowSmoothing = 12f;

        public Camera PlayerCamera { get; private set; }
        public Vector2 PlayerPosition { get; private set; }
        public bool IsRotating { get { return _rotating; } }
        public bool CursorLocked { get { return _cursorLocked; } }

        private CharacterController _controller;
        private float _yaw;
        private float _pitch = 18f;
        private float _targetDistance;
        private bool _cursorLocked = true;
        private bool _rotating;
        private float _lastReport;
        private Vector3 _lastReported;

        void Awake()
        {
            if (transport == null)
                transport = FindObjectOfType<TransportClient>();

            _controller = gameObject.GetComponent<CharacterController>();
            if (_controller == null)
                _controller = gameObject.AddComponent<CharacterController>();
            _controller.height = 1.8f;
            _controller.radius = 0.4f;
            _controller.center = new Vector3(0f, 0.9f, 0f);
            _targetDistance = cameraDistance;

            if (PlayerCamera == null)
                PlayerCamera = Camera.main;
            if (PlayerCamera == null)
            {
                var go = new GameObject("PlayerCamera");
                PlayerCamera = go.AddComponent<Camera>();
            }
            PlayerCamera.transform.SetParent(transform, false);

            Cursor.lockState = CursorLockMode.Locked;
            Cursor.visible = false;
        }

        void Update()
        {
            if (Input.GetKeyDown(KeyCode.Escape))
            {
                _cursorLocked = !_cursorLocked;
                Cursor.lockState = _cursorLocked ? CursorLockMode.Locked : CursorLockMode.None;
                Cursor.visible = !_cursorLocked;
            }

            if (Input.GetMouseButtonDown(1)) _rotating = true;
            if (Input.GetMouseButtonUp(1)) _rotating = false;

            if (_cursorLocked || _rotating)
            {
                _yaw += Input.GetAxis("Mouse X") * mouseSensitivity;
                _pitch = Mathf.Clamp(_pitch - Input.GetAxis("Mouse Y") * mouseSensitivity, -15f, 65f);
            }

            Move();

            UpdateCameraZoom();

            transform.rotation = Quaternion.Euler(0f, _yaw, 0f);

            PlayerPosition = new Vector2(transform.position.x / worldScale, transform.position.z / worldScale);
            if (transport != null && Time.time - _lastReport >= updateInterval)
            {
                Vector3 current = transform.position;
                if (Vector3.Distance(current, _lastReported) > 0.15f * worldScale || _lastReported == Vector3.zero)
                {
                    transport.SendPlayerUpdate(PlayerPosition.x, PlayerPosition.y);
                    _lastReported = current;
                }
                _lastReport = Time.time;
            }
        }

        void Move()
        {
            Vector3 forward = Vector3.ProjectOnPlane(PlayerCamera.transform.forward, Vector3.up).normalized;
            Vector3 right = Vector3.ProjectOnPlane(PlayerCamera.transform.right, Vector3.up).normalized;
            float h = Input.GetAxisRaw("Horizontal");
            float v = Input.GetAxisRaw("Vertical");
            Vector3 wishDir = (forward * v + right * h).normalized;

            float speed = Input.GetKey(KeyCode.LeftShift) ? sprintSpeed : moveSpeed;
            Vector3 motion = wishDir * speed * worldScale;
            if (_controller.isGrounded) motion.y = -0.5f;

            _controller.Move(motion * Time.deltaTime);
        }

        void UpdateCameraZoom()
        {
            float scroll = Input.GetAxis("Mouse ScrollWheel");
            if (Mathf.Abs(scroll) > 0.0001f)
                _targetDistance = Mathf.Clamp(_targetDistance - scroll * zoomSpeed, minCameraDistance, maxCameraDistance);
            cameraDistance = Mathf.Lerp(cameraDistance, _targetDistance, Mathf.Min(1f, 10f * Time.deltaTime));
        }

        void LateUpdate()
        {
            Quaternion camRot = Quaternion.Euler(_pitch, _yaw, 0f);
            Vector3 offset = camRot * new Vector3(0f, 0f, -cameraDistance);
            Vector3 desired = transform.position + offset + new Vector3(0f, cameraHeight, 0f);

            // Pull the camera in front of walls/trees/ground and stop it from
            // passing through the player's own collider.
            Vector3 from = transform.position + Vector3.up * (cameraHeight * 0.8f);
            Vector3 dir = desired - from;
            float maxDist = dir.magnitude;
            if (maxDist > 0.0001f)
            {
                RaycastHit hit;
                if (Physics.Raycast(from, dir.normalized, out hit, maxDist) && !IsSelf(hit.collider.transform))
                    desired = hit.point - dir.normalized * 0.2f;
            }

            PlayerCamera.transform.position = Vector3.Lerp(
                PlayerCamera.transform.position, desired,
                Mathf.Min(1f, cameraFollowSmoothing * Time.deltaTime));
            PlayerCamera.transform.rotation = camRot;
        }

        bool IsSelf(Transform t)
        {
            Transform p = t;
            while (p != null)
            {
                if (p == PlayerCamera.transform.parent) return true;
                p = p.parent;
            }
            return false;
        }
    }
}