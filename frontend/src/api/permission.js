import request from './index'

/**
 * 获取权限列表（带分页）
 * @param {object} params { page_num, page_size }
 */
export function getPermissionList(params) {
  return request({
    url: '/permissions',
    method: 'get',
    params
  })
}

/**
 * 获取单个权限
 * @param {number} id 权限ID
 */
export function getPermission(id) {
  return request({
    url: `/permissions/${id}`,
    method: 'get'
  })
}

/**
 * 添加权限
 * @param {object} data 权限信息
 */
export function addPermission(data) {
  return request({
    url: '/permissions',
    method: 'post',
    data
  })
}

/**
 * 更新权限
 * @param {number} id 权限ID
 * @param {object} data 更新信息
 */
export function updatePermission(id, data) {
  return request({
    url: `/permissions/${id}`,
    method: 'put',
    data
  })
}

/**
 * 删除单个权限
 * @param {number} id 权限ID
 */
export function deletePermission(id) {
  return request({
    url: `/permissions/${id}`,
    method: 'delete'
  })
}

/**
 * 批量删除权限
 * @param {array} ids 权限ID列表
 */
export function batchDeletePermissions(ids) {
  return request({
    url: '/permissions',
    method: 'delete',
    data: ids
  })
}