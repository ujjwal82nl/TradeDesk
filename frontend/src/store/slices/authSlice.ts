import { createSlice, PayloadAction } from '@reduxjs/toolkit';

interface AuthState {
  user:          { id: number; email: string; full_name: string } | null;
  accessToken:   string | null;
  refreshToken:  string | null;
  isAuthenticated: boolean;
}

const loadFromStorage = (): AuthState => {
  try {
    return {
      user:            JSON.parse(localStorage.getItem('user') || 'null'),
      accessToken:     localStorage.getItem('accessToken'),
      refreshToken:    localStorage.getItem('refreshToken'),
      isAuthenticated: !!localStorage.getItem('accessToken'),
    };
  } catch {
    return { user: null, accessToken: null, refreshToken: null, isAuthenticated: false };
  }
};

const authSlice = createSlice({
  name: 'auth',
  initialState: loadFromStorage(),
  reducers: {
    setCredentials(state, { payload }: PayloadAction<{ user: any; access_token: string; refresh_token: string }>) {
      state.user            = payload.user;
      state.accessToken     = payload.access_token;
      state.refreshToken    = payload.refresh_token;
      state.isAuthenticated = true;
      localStorage.setItem('user',         JSON.stringify(payload.user));
      localStorage.setItem('accessToken',  payload.access_token);
      localStorage.setItem('refreshToken', payload.refresh_token);
    },
    logout(state) {
      state.user = null; state.accessToken = null; state.refreshToken = null; state.isAuthenticated = false;
      localStorage.removeItem('user');
      localStorage.removeItem('accessToken');
      localStorage.removeItem('refreshToken');
    },
  },
});

export const { setCredentials, logout } = authSlice.actions;
export default authSlice.reducer;
