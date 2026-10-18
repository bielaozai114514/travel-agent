import request from './index'

export const getAttractionPhoto = (name) => {
  return request({
    url: '/poi/photo',
    method: 'get',
    params: { name }
  })
}

export const searchPOI = (keywords, city = '北京') => {
  return request({
    url: '/poi/search',
    method: 'get',
    params: { keywords, city }
  })
}

export const getPOIDetail = (poiId) => {
  return request({
    url: `/poi/detail/${poiId}`,
    method: 'get'
  })
}

export default {
  getAttractionPhoto,
  searchPOI,
  getPOIDetail
}
