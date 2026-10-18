<template>
  <div class="role-list-container">
    <!-- 新增和批量删除按钮 -->
    <div class="role-list-header">
      <el-button
        type="primary"
        icon="Plus"
        @click="handleAdd"
        v-permission="'roles:write'"
      >
        添加角色
      </el-button>
      <el-button
        type="danger"
        icon="Delete"
        @click="handleBatchDelete"
        v-permission="'roles:write'"
        :disabled="selectedIds.length === 0"
      >
        批量删除
      </el-button>
    </div>

    <!-- 角色列表 -->
    <el-table
      :data="roleList"
      border
      stripe
      v-loading="loading"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" />
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="角色名称" min-width="120" />
      <el-table-column prop="description" label="角色描述" min-width="200" />
      <el-table-column label="操作" min-width="220">
        <template v-slot="scope">
          <el-button
            type="primary"
            size="small"
            icon="Edit"
            @click="handleEdit(scope.row)"
            v-permission="'roles:write'"
          >
            编辑
          </el-button>
          <el-button
            type="warning"
            size="small"
            icon="Key"
            @click="handlePermission(scope.row)"
            v-permission="'roles:write'"
          >
            权限
          </el-button>
          <el-button
            type="danger"
            size="small"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-permission="'roles:write'"
            :disabled="scope.row.name === 'admin'"
            :title="scope.row.name === 'admin' ? '系统管理员角色不可删除' : ''"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <el-pagination
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      :current-page="pageParams.page_num"
      :page-sizes="[5, 10, 20, 50]"
      :page-size="pageParams.page_size"
      layout="total, sizes, prev, pager, next, jumper"
      :total="total"
      class="role-pagination"
    >
    </el-pagination>

    <!-- 添加/编辑角色弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      @close="resetForm"
    >
      <RoleForm
        ref="roleFormRef"
        :role-info="currentRole"
        @submit="handleFormSubmit"
      />
    </el-dialog>

    <!-- 角色权限配置弹窗 -->
    <el-dialog
      v-model="permissionDialogVisible"
      title="配置角色权限"
      width="700px"
    >
      <RolePermission
        :role-id="currentRoleId"
        @success="handlePermissionSuccess"
        @cancel="permissionDialogVisible = false"
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  getRoleList as fetchRoleList,
  deleteRole,
  batchDeleteRoles,
  addRole,
  updateRole,
} from "@/api/role";
import RoleForm from "./RoleForm.vue";
import RolePermission from "./RolePermission.vue";
import { permissionDirective } from "@/utils/permission";
import { useUserStore } from "@/pinia/userStore";

const userStore = useUserStore();
const vPermission = permissionDirective(userStore);

// 响应式变量定义
const loading = ref(false);
const roleList = ref([]);
const total = ref(0);
const selectedIds = ref([]);

// 分页参数
const pageParams = reactive({
  page_num: 1,
  page_size: 10,
});

// 弹窗相关变量
const dialogVisible = ref(false);
const permissionDialogVisible = ref(false);
const dialogTitle = ref("添加角色");
const currentRole = ref({});
const currentRoleId = ref(0);

// 表单引用
const roleFormRef = ref(null);

/**
 * 获取角色列表
 */
const getRoleList = async () => {
  try {
    loading.value = true;
    const params = {
      ...pageParams,
    };
    const res = await fetchRoleList(params);
    roleList.value = res.data.list || [];
    total.value = res.data.total || 0;
  } catch (error) {
    console.error("获取角色列表失败：", error);
    ElMessage.error("获取角色列表失败");
  } finally {
    loading.value = false;
  }
};

/**
 * 处理分页大小变化
 */
const handleSizeChange = (val) => {
  pageParams.page_size = val;
  getRoleList();
};

/**
 * 处理页码变化
 */
const handleCurrentChange = (val) => {
  pageParams.page_num = val;
  getRoleList();
};

/**
 * 处理选择变化
 */
const handleSelectionChange = (val) => {
  selectedIds.value = val.map((item) => item.id);
};

/**
 * 处理添加
 */
const handleAdd = () => {
  dialogTitle.value = "添加角色";
  currentRole.value = {};
  dialogVisible.value = true;
};

/**
 * 处理编辑
 */
const handleEdit = (row) => {
  dialogTitle.value = "编辑角色";
  currentRole.value = { ...row };
  dialogVisible.value = true;
};

/**
 * 处理权限配置
 */
const handlePermission = (row) => {
  currentRoleId.value = row.id;
  permissionDialogVisible.value = true;
};

/**
 * 处理删除
 */
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm("此操作将永久删除该角色, 是否继续?", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning",
    });
    await deleteRole(row.id);
    ElMessage.success("删除成功");
    getRoleList();
  } catch (error) {
    if (error !== "cancel") {
      console.error("删除失败：", error);
      ElMessage.error("删除失败");
    }
  }
};

/**
 * 处理批量删除
 */
const handleBatchDelete = async () => {
  try {
    // 检查是否包含admin角色
    const hasAdmin = roleList.value.some(role => selectedIds.value.includes(role.id) && role.name === 'admin');
    if (hasAdmin) {
      ElMessage.warning("系统管理员角色不可删除");
      return;
    }
    
    await ElMessageBox.confirm(
      "此操作将永久删除选中的角色, 是否继续?",
      "提示",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
    await batchDeleteRoles(selectedIds.value);
    ElMessage.success("批量删除成功");
    getRoleList();
  } catch (error) {
    if (error !== "cancel") {
      console.error("批量删除失败：", error);
      ElMessage.error("批量删除失败");
    }
  }
};

/**
 * 处理表单提交
 */
const handleFormSubmit = async (formData) => {
  try {
    if (currentRole.value.id) {
      // 编辑模式
      await updateRole(currentRole.value.id, formData);
      ElMessage.success("编辑角色成功");
    } else {
      // 新增模式
      await addRole(formData);
      ElMessage.success("新增角色成功");
    }
    dialogVisible.value = false;
    getRoleList();
  } catch (error) {
    console.error(`${currentRole.value.id ? "编辑" : "新增"}角色失败：`, error);
    ElMessage.error(`${currentRole.value.id ? "编辑" : "新增"}角色失败`);
  }
};

/**
 * 重置表单
 */
const resetForm = () => {
  currentRole.value = {};
  if (
    roleFormRef.value &&
    typeof roleFormRef.value.handleReset === "function"
  ) {
    roleFormRef.value.handleReset();
  }
};

/**
 * 处理权限配置成功
 */
const handlePermissionSuccess = () => {
  permissionDialogVisible.value = false;
  ElMessage.success("权限配置成功");
};

// 初始化
onMounted(() => {
  getRoleList();
});
</script>

<style scoped>
.role-list-container {
  padding: 24px;
}

.role-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.role-list-header .el-button {
  display: flex;
  align-items: center;
  gap: 6px;
}

.role-pagination {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e9ecef;
}

/* 表格操作按钮样式 */
:deep(.el-table .cell) {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

:deep(.el-table .el-button) {
  padding: 6px 12px;
  font-size: 13px;
}

:deep(.el-table .el-button .el-icon) {
  font-size: 14px;
}
</style>
