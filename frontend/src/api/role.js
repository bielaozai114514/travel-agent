import request from './index'

/**
 * 获取角色列表（带分页）
 * @param {object} params { page_num, page_size }
 */
export function getRoleList(params) {
  return request({
    url: '/roles',
    method: 'get',
    params
  })
}

/**
 * 获取单个角色
 * @param {number} id 角色ID
 */
export function getRole(id) {
  return request({
    url: `/roles/${id}`,
    method: 'get'
  })
}

/**
 * 添加角色
 * @param {object} data 角色信息
 */
export function addRole(data) {
  return request({
    url: '/roles',
    method: 'post',
    data
  })
}

/**
 * 更新角色
 * @param {number} id 角色ID
 * @param {object} data 更新信息
 */
export function updateRole(id, data) {
  return request({
    url: `/roles/${id}`,
    method: 'put',
    data
  })
}

/**
 * 删除单个角色
 * @param {number} id 角色ID
 */
export function deleteRole(id) {
  return request({
    url: `/roles/${id}`,
    method: 'delete'
  })
}

/**
 * 批量删除角色
 * @param {array} ids 角色ID列表
 */
export function batchDeleteRoles(ids) {
  return request({
    url: '/roles',
    method: 'delete',
    data: ids
  })
}

/**
 * 获取角色权限
 * @param {number} id 角色ID
 */
export function getRolePermissions(id) {
  return request({
    url: `/roles/${id}/permissions`,
    method: 'get'
  })
}

/**
 * 绑定角色权限
 * @param {number} id 角色ID
 * @param {array} permIds 权限ID列表
 */
export function bindRolePermissions(id, permIds) {
  return request({
    url: `/roles/${id}/permissions`,
    method: 'post',
    data: permIds
  })
}

/**
 * 解绑角色权限
 * @param {number} id 角色ID
 * @param {array} permIds 权限ID列表
 */
export function unbindRolePermissions(id, permIds) {
  return request({
    url: `/roles/${id}/permissions`,
    method: 'delete',
    data: permIds
  })
}