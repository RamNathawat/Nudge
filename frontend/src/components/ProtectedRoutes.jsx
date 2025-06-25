import { getToken } from "../utils/auth";

function ProtectedRoute({ children }) {
  return getToken() ? children : <p>Please log in to continue.</p>;
}

export default ProtectedRoute;