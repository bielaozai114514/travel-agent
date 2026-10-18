import request from './index'

/**
 * 用户登录
 * @param {object} data { email, password }
 */
export function login(data) {
    // 注意：FastAPI 的 OAuth2PasswordRequestForm 要求用 form-data 格式
    const formData = new FormData()
    formData.append('username', data.email)  // 对应后端的 form_data.username
    formData.append('password', data.password)

    return request({
        url: '/users/login',
        method: 'post',
        data: formData,
        headers: {
            'Content-Type': 'multipart/form-data'
        }
    })
}

/**
 * 获取用户列表（带分页）
 * @param {object} params { page_num, page_size, username, email }
 */
export function getUserList(params) {
    return request({
        url: '/users',
        method: 'get',
        params
    })
}

/**
 * 获取单个用户
 * @param {number} id 用户ID
 */
export function getUser(id) {
    return request({
        url: `/users/${id}`,
        method: 'get'
    })
}

/**
 * 添加用户
 * @param {object} data 用户信息
 */
export function addUser(data) {
    return request({
        url: '/users/register',
        method: 'post',
        data
    })
}

/**
 * 更新用户
 * @param {number} id 用户ID
 * @param {object} data 更新信息
 */
export function updateUser(id, data) {
    return request({
        url: `/users/${id}`,
        method: 'put',
        data
    })
}

/**
 * 删除单个用户
 * @param {number} id 用户ID
 */
export function deleteUser(id) {
    return request({
        url: `/users/${id}`,
        method: 'delete'
    })
}

/**
 * 批量删除用户
 * @param {array} ids 用户ID列表
 */
export function batchDeleteUsers(ids) {
    return request({
        url: '/users',
        method: 'delete',
        data: ids
    })
}

/**
 * 获取用户角色
 * @param {number} id 用户ID
 */
export function getUserRoles(id) {
    return request({
        url: `/users/${id}/roles`,
        method: 'get'
    })
}

/**
 * 绑定用户角色
 * @param {number} id 用户ID
 * @param {array} roleIds 角色ID列表
 */
export function bindUserRoles(id, roleIds) {
    return request({
        url: `/users/${id}/roles`,
        method: 'post',
        data: roleIds
    })
}

/**
 * 解绑用户角色
 * @param {number} id 用户ID
 * @param {array} roleIds 角色ID列表
 */
export function unbindUserRoles(id, roleIds) {
    return request({
        url: `/users/${id}/roles`,
        method: 'delete',
        data: roleIds
    })
}

/**
 * 获取当前登录用户信息
 */
export function getCurrentUser() {
    return request({
        url: '/users/current',
        method: 'get'
    })
}