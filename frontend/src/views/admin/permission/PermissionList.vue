  <template>
  <div class="permission-list-container">
    <!-- 工具栏：搜索 + 新增按钮 -->
    <div class="permission-toolbar">
      <!-- <el-input
          v-model="searchForm.keyword"
          placeholder="请输入权限名称/标识搜索"
          style="width: 300px; margin-right: 10px"
          clearable
          @keyup.enter="handleSearch"
        /> -->
      <el-button
        type="primary"
        icon="plus"
        @click="handleAdd"
        v-permission="'permissions:write'"
      >
        新增权限
      </el-button>
      <el-button
        type="danger"
        icon="delete"
        @click="handleBatchDelete"
        :disabled="selectedPermissions.length === 0"
        v-permission="'permissions:write'"
      >
        批量删除
      </el-button>
    </div>

    <!-- 权限列表表格 -->
    <el-table
      v-loading="loading"
      :data="permissionList"
      border
      stripe
      @selection-change="handleSelectionChange"
      style="width: 100%; margin-top: 10px"
    >
      <el-table-column type="selection" width="55" />
      <el-table-column prop="id" label="权限ID" width="250" align="center" />
      <el-table-column prop="scope" label="权限标识" min-width="200" />
      <el-table-column prop="description" label="权限描述" min-width="250" />
      <el-table-column label="操作" width="250" align="center">
        <template #default="scope">
          <el-button
            type="primary"
            size="small"
            icon="edit"
            @click="handleEdit(scope.row)"
            v-permission="'permissions:write'"
          >
            编辑
          </el-button>
          <el-button
            type="danger"
            size="small"
            icon="delete"
            @click="handleDelete(scope.row.id)"
            v-permission="'permissions:delete'"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页控件 -->
    <el-pagination
      v-if="total > 0"
      :current-page="pagination.page_num"
      :page-size="pagination.page_size"
      :total="total"
      layout="total, sizes, prev, pager, next, jumper"
      @size-change="handleSizeChange"
      @current-change="handleCurrentChange"
      style="margin-top: 20px; text-align: right"
    />

    <!-- 新增/编辑权限弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="600px"
      @close="handleDialogClose"
    >
      <el-form
        ref="permissionFormRef"
        :model="permissionForm"
        :rules="permissionRules"
        label-width="100px"
      >
        <el-form-item label="权限标识" prop="scope">
          <el-input
            v-model="permissionForm.scope"
            placeholder="请输入权限标识（如：users:edit）"
            tooltip="权限标识格式：模块:操作，例：users:read/roles:write"
            :disabled="dialogTitle === '编辑权限'"
          />
        </el-form-item>
        <el-form-item label="权限描述" prop="description">
          <el-input
            v-model="permissionForm.description"
            type="textarea"
            rows="3"
            placeholder="请输入权限描述"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button
          type="primary"
          @click="handleFormSubmit"
          :loading="formLoading"
        >
          确认
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
// 导入权限相关接口（仅CRUD）
import {
  getPermissionList,
  addPermission,
  updatePermission,
  deletePermission,
  batchDeletePermissions,
} from "@/api/permission";

// 权限认证
import { permissionDirective } from "@/utils/permission";
import { useUserStore } from "@/pinia/userStore";
const userStore = useUserStore();
const vPermission = permissionDirective(userStore);

// ========== 基础响应式变量 ==========
// 列表加载状态
const loading = ref(false);
// 权限列表数据
const permissionList = ref([]);
// 分页参数
const pagination = reactive({
  page_num: 1,
  page_size: 10,
});
// 总条数
const total = ref(0);
// 搜索表单
const searchForm = reactive({
  keyword: "",
});
// 选中的权限（批量删除用）
const selectedPermissions = ref([]);

// ========== 新增/编辑弹窗相关
const dialogVisible = ref(false);
const dialogTitle = ref("");
const formLoading = ref(false);
const permissionFormRef = ref(null);
// 权限表单数据
const permissionForm = reactive({
  id: "",
  scope: "",
  description: "",
});
// 表单校验规则
const permissionRules = reactive({
  scope: [
    { required: true, message: "请输入权限标识", trigger: "blur" },
    {
      pattern: /^[a-z]+:[a-z]+$/,
      message: "权限标识格式：模块:操作（小写），例：users:read",
      trigger: "blur",
    },
  ],
  description: [{ required: true, message: "请输入权限描述", trigger: "blur" }],
});

// 获取权限列表
const fetchPermissionList = async () => {
  loading.value = true;
  try {
    // 构造请求参数：分页
    const params = {
      ...pagination,
    };
    const res = await getPermissionList(params);
    permissionList.value = res.data.list || [];
    total.value = res.data.total || 0;
  } catch (error) {
    ElMessage.error("获取权限列表失败");
    console.error("获取权限列表失败：", error);
    permissionList.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
};

// ========== 工具栏方法 ==========
// 搜索
const handleSearch = () => {
  pagination.page_num = 1; // 搜索时重置页码
  fetchPermissionList();
};
// 分页尺寸变化
const handleSizeChange = (val) => {
  pagination.page_size = val;
  fetchPermissionList();
};
// 分页页码变化
const handleCurrentChange = (val) => {
  pagination.page_num = val;
  fetchPermissionList();
};
// 表格选择变化（批量删除）
const handleSelectionChange = (val) => {
  selectedPermissions.value = val;
};

// ========== 新增/编辑权限 ==========
// 新增权限
const handleAdd = () => {
  dialogTitle.value = "新增权限";
  // 重置表单
  permissionFormRef.value?.resetFields();
  Object.assign(permissionForm, {
    id: "",
    scope: "",
    description: "",
  });
  dialogVisible.value = true;
};
// 编辑权限
const handleEdit = (row) => {
  dialogTitle.value = "编辑权限";
  // 填充表单数据
  Object.assign(permissionForm, {
    id: row.id,
    scope: row.scope, // 填充scope但不允许修改
    description: row.description,
  });
  dialogVisible.value = true;
};
// 表单提交（新增/编辑）
const handleFormSubmit = async () => {
  // 表单校验
  try {
    await permissionFormRef.value.validate();
  } catch (error) {
    ElMessage.warning("请完善表单必填项");
    return;
  }

  formLoading.value = true;
  try {
    if (permissionForm.id) {
      // 编辑权限
      await updatePermission(permissionForm.id, permissionForm);
      ElMessage.success("编辑权限成功");
    } else {
      // 新增权限
      await addPermission(permissionForm);
      ElMessage.success("新增权限成功");
    }
    // 关闭弹窗 + 刷新列表
    dialogVisible.value = false;
    fetchPermissionList();
  } catch (error) {
    ElMessage.error(`${permissionForm.id ? "编辑" : "新增"}权限失败`);
    console.error(`${permissionForm.id ? "编辑" : "新增"}权限失败：`, error);
  } finally {
    formLoading.value = false;
  }
};
// 关闭弹窗重置表单
const handleDialogClose = () => {
  permissionFormRef.value?.resetFields();
};

// ========== 删除权限 ==========
// 单个删除
const handleDelete = async (id) => {
  try {
    await ElMessageBox.confirm("确定要删除该权限吗？", "温馨提示", {
      confirmButtonText: "确定",
      cancelButtonText: "取消",
      type: "warning",
    });
    await deletePermission(id);
    ElMessage.success("删除权限成功");
    fetchPermissionList();
  } catch (error) {
    if (error !== "cancel") {
      // 排除取消操作
      ElMessage.error("删除权限失败");
      console.error("删除权限失败：", error);
    }
  }
};
// 批量删除
const handleBatchDelete = async () => {
  if (selectedPermissions.value.length === 0) {
    ElMessage.warning("请选择要删除的权限");
    return;
  }

  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedPermissions.value.length} 个权限吗？`,
      "温馨提示",
      {
        confirmButtonText: "确定",
        cancelButtonText: "取消",
        type: "warning",
      }
    );
    // 提取选中的权限ID
    const ids = selectedPermissions.value.map((item) => item.id);
    await batchDeletePermissions(ids);
    ElMessage.success("批量删除权限成功");
    fetchPermissionList();
  } catch (error) {
    if (error !== "cancel") {
      ElMessage.error("批量删除权限失败");
      console.error("批量删除权限失败：", error);
    }
  }
};

// ========== 初始化 ==========
onMounted(() => {
  fetchPermissionList();
});
</script>

  <style scoped>
.permission-list-container {
  padding: 24px;
}

.permission-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  padding: 16px 20px;
  background: #f5f7fa;
  border-radius: 8px;
  border: 1px solid #e4e7ed;
}

.permission-toolbar .el-button {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* 分页样式 */
:deep(.el-pagination) {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #e9ecef;
  justify-content: flex-end;
}

/* 表格操作按钮样式 */
:deep(.el-table .cell) {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

:deep(.el-table .el-button) {
  padding: 6px 12px;
  font-size: 13px;
}

:deep(.el-table .el-button .el-icon) {
  font-size: 14px;
}
</style>