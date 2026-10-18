<template>
  <div class="user-list-container">
    <!-- 新增和批量删除按钮 -->
    <div class="user-list-header">
      <el-button
        type="primary"
        icon="Plus"
        @click="handleAdd"
        v-permission="'users:write'"
      >
        添加用户
      </el-button>
      <el-button
        type="danger"
        icon="Delete"
        @click="handleBatchDelete"
        v-permission="'users:write'"
        :disabled="selectedIds.length === 0"
      >
        批量删除
      </el-button>
    </div>

    <!-- 搜索栏 -->
    <!-- <el-form :inline="true" :model="searchForm" class="user-search-form">
      <el-form-item label="用户名">
        <el-input
          v-model="searchForm.username"
          placeholder="请输入用户名"
          clearable
        />
      </el-form-item>
      <el-form-item label="邮箱">
        <el-input
          v-model="searchForm.email"
          placeholder="请输入邮箱"
          clearable
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="getUserList">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form> -->

    <!-- 用户列表 -->
    <el-table
      :data="userList"
      border
      stripe
      v-loading="loading"
      @selection-change="handleSelectionChange"
    >
      <el-table-column type="selection" width="55" />
      <!-- 复选框列：用于批量操作 -->
      <el-table-column prop="id" label="ID" width="80" />
      <!-- 显示用户ID -->
      <el-table-column prop="username" label="用户名" min-width="120" />
      <!-- 显示用户名 -->
      <el-table-column prop="email" label="邮箱" min-width="150" />
      <!-- 显示邮箱 -->
      <el-table-column label="操作" min-width="150">
        <template v-slot="scope">
          <!-- 作用域插槽：scope.row = 当前行的用户数据 -->
          <el-button
            type="primary"
            size="small"
            icon="Edit"
            @click="handleEdit(scope.row)"
            v-permission="'users:write'"
          >
            编辑
          </el-button>
          <el-button
            type="danger"
            size="small"
            icon="Delete"
            @click="handleDelete(scope.row)"
            v-permission="'users:write'"
            :disabled="scope.row.username === 'admin'"
            :title="scope.row.username === 'admin' ? '系统管理员账户不可删除' : ''"
          >
            删除
          </el-button>
          <el-button
            type="warning"
            size="small"
            icon="User"
            @click="handleRole(scope.row)"
            v-permission="'roles:write'"
          >
            角色
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
      class="user-pagination"
    >
    </el-pagination>

    <!-- 添加/编辑用户弹窗 -->
    <!-- 弹窗显隐：绑定 dialogVisible（true=显示，false=隐藏） -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="500px"
      @close="resetForm"
    >
      <!-- 子组件：UserForm（表单组件） -->
      <UserForm
        ref="userFormRef"
        :user-info="currentUser"
        @submit="handleFormSubmit"
      />
    </el-dialog>

    <!-- 用户角色配置弹窗 -->
    <el-dialog v-model="roleDialogVisible" title="配置用户角色" width="500px">
      <UserRole
        :user-id="currentUserId"
        @success="
          roleDialogVisible = false;
          getUserList();
        "
      />
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import {
  getUserList as fetchUserList,
  deleteUser,
  batchDeleteUsers,
  addUser,
  updateUser,
} from "@/api/user";
// 导入子组件
import UserForm from "./UserForm.vue";
import UserRole from "./UserRole.vue";
import PermissionBtn from "@/components/PermissionBtn.vue";

// 导入权限相关
import { permissionDirective } from "@/utils/permission";
import { useUserStore } from "@/pinia/userStore";
const userStore = useUserStore();
const vPermission = permissionDirective(userStore);

// 响应式变量定义
const loading = ref(false); // 加载状态
const userList = ref([]); // 用户列表
const total = ref(0); // 总数
const selectedIds = ref([]); // 选中的ID

// 分页参数
const pageParams = reactive({
  page_num: 1,
  page_size: 10,
});

// 搜索表单
const searchForm = reactive({
  username: "",
  email: "",
});

// 弹窗相关变量

const dialogVisible = ref(false); // 新增/编辑弹窗显隐
const roleDialogVisible = ref(false); // 角色配置弹窗显隐
const dialogTitle = ref("添加用户"); // 弹窗标题
const currentUser = ref({}); // 当前用户
const originalUser = ref({}); // 保存编辑前的原始数据
const currentUserId = ref(0); // 当前用户ID

// 表单引用 绑定 UserForm 子组件
const userFormRef = ref(null);

/**
 * 获取用户列表
 */
const getUserList = async () => {
  try {
    loading.value = true; // 显示加载动画
    // 合并分页和搜索参数
    const params = {
      ...pageParams,
    };
    const res = await fetchUserList(params);
    userList.value = res.data.list;
    total.value = res.data.total;
  } catch (error) {
    console.error("获取用户列表失败：", error);
  } finally {
    loading.value = false;
  }
};

/**
 * 处理分页大小变化
 */
const handleSizeChange = (val) => {
  pageParams.page_size = val;
  getUserList();
};

/**
 * 处理页码变化
 */
const handleCurrentChange = (val) => {
  pageParams.page_num = val;
  getUserList();
};

/**
 * 重置搜索
 */
const resetSearch = () => {
  searchForm.username = "";
  searchForm.email = "";
  getUserList();
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
  dialogTitle.value = "添加用户";
  currentUser.value = {};
  dialogVisible.value = true;
};

/**
 * 处理编辑
 */
const handleEdit = (row) => {
  dialogTitle.value = "编辑用户";
  currentUser.value = { ...row };
  originalUser.value = { ...row }; // 保存原始数据
  // console.log(currentUser.value.id)
  dialogVisible.value = true;
};

/**
 * 处理角色配置
 */
const handleRole = (row) => {
  currentUserId.value = row.id;
  console.log(row.id);
  roleDialogVisible.value = true;
};

/**
 * 处理删除
 */
const handleDelete = async (row) => {
  try {
    await ElMessageBox.confirm("此操作将永久删除该用户, 是否继续?", "提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning",
    });
    await deleteUser(row.id);
    ElMessage.success("删除成功");
    getUserList();
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
    // 检查是否包含admin用户
    const hasAdmin = userList.value.some(user => selectedIds.value.includes(user.id) && user.username === 'admin');
    if (hasAdmin) {
      ElMessage.warning("系统管理员账户不可删除");
      return;
    }
    
    await ElMessageBox.confirm(
      "此操作将永久删除选中的用户, 是否继续?",
      "提示",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
    await batchDeleteUsers(selectedIds.value);
    ElMessage.success("批量删除成功");
    getUserList();
  } catch (error) {
    if (error !== "cancel") {
      console.error("批量删除失败：", error);
      ElMessage.error("批量删除失败");
    }
  }
};

/**
 * 筛选只修改过的字段（核心工具函数）
 * @param {Object} original - 编辑前的原始数据
 * @param {Object} current - 编辑后的表单数据
 * @returns {Object} 只有修改过的字段
 */
const getChangedFields = (original, current) => {
  const changedData = {};

  // 遍历当前表单的所有字段（只对比需要的字段，排除password等不需要的）
  const compareFields = ["username", "email"]; // 可根据后端需求调整（比如加full_name等）

  compareFields.forEach((field) => {
    // 对比原始值和当前值：值不同才保留
    if (current[field] !== original[field]) {
      changedData[field] = current[field];
    }
  });

  // 特殊处理：空字符串/空值不传给后端（比如用户清空了但后端不需要）
  Object.keys(changedData).forEach((key) => {
    if (changedData[key] === "" || changedData[key] === undefined) {
      delete changedData[key];
    }
  });

  return changedData;
};

/**
 * 处理表单提交
 */
const handleFormSubmit = async (formData) => {
  try {
    if (currentUser.value.id) {
      // 编辑模式：只传修改的字段
      // 筛选出变化的字段
      const changedData = getChangedFields(originalUser.value, formData);
      // 没有修改任何字段时，直接提示并关闭弹窗
      if (Object.keys(changedData).length === 0) {
        ElMessage.info("未修改任何字段，无需提交");
        dialogVisible.value = false;
        return;
      }
      // 有 变化字段：调用 updateUser 接口
      await updateUser(currentUser.value.id, changedData);
      ElMessage.success("编辑用户成功");
    } else {
      // 无 id → 新增模式：调用 addUser 接口
      await addUser(formData);
      ElMessage.success("新增用户成功");
    }
    dialogVisible.value = false; // 关闭弹窗
    getUserList(); // 重新获取列表（刷新数据）
  } catch (error) {
    console.error(`${currentUser.value.id ? "编辑" : "新增"}用户失败：`, error);
    ElMessage.error(`${currentUser.value.id ? "编辑" : "新增"}用户失败`);
  }
};

/**
 * 重置表单
 */
const resetForm = () => {
  currentUser.value = {}; // 清空当前用户数据（兜底）
  // 调用子组件的 handleReset 方法（UserForm 里暴露的方法名）
  if (
    userFormRef.value &&
    typeof userFormRef.value.handleReset === "function"
  ) {
    userFormRef.value.handleReset();
  }
};

// 初始化
onMounted(() => {
  getUserList();
});
</script>

<style scoped>
.user-list-container {
  padding: 24px;
}

.user-list-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.user-list-header .el-button {
  display: flex;
  align-items: center;
  gap: 6px;
}

.user-search-form {
  margin-bottom: 20px;
  padding: 20px;
  background: #f8f9fa;
  border-radius: 12px;
  border: 1px solid #e9ecef;
}

.user-pagination {
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