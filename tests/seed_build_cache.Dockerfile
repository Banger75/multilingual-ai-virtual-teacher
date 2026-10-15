FROM subject_specific_virtual_teacher-virtual-teacher:latest
RUN --mount=type=cache,id=virtual_teacher_uv,target=/uv-cache \
    cp -a /root/.cache/uv/. /uv-cache/
