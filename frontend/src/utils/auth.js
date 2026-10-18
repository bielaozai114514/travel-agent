// Token 键名
const TOKEN_KEY = 'access_token'

/**
 * 获取 Token
 */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

/**
 * 设置 Token
 * @param {string} token 
 */
export function setToken(token) {
  return localStorage.setItem(TOKEN_KEY, token)
}

/**
 * 移除 Token
 */
export function removeToken() {
  return localStorage.removeItem(TOKEN_KEY)
}

/**
 * 获取用户权限
 */
export function getScopes() {
  return JSON.parse(localStorage.getItem('user_scopes') || '[]')
}

/**
 * 设置用户权限
 * @param {array} scopes 
 */
export function setScopes(scopes) {
  return localStorage.setItem('user_scopes', JSON.stringify(scopes))
}