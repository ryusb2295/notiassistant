<script setup>
import { useRouter } from 'vue-router'
import Icon from '../components/Icon.vue'

const router = useRouter()
</script>

<template>
  <header class="head back-head">
    <button class="icon-btn" aria-label="뒤로" @click="router.back()"><Icon name="back" :size="22" /></button>
    <div class="inner"><h1 class="title-md">개인정보 처리 안내</h1></div>
  </header>
  <main class="main">
    <section class="card policy">
      <h2>수집 항목</h2>
      <p>아이디, 비밀번호(암호화 저장), 이름, 프로필 사진(올린 경우), 학과, 학년, 관심사, 구독 게시판, 저장한 일정, 신청 현황(신청 예정·완료 표시)</p>
      <h2>이용 목적</h2>
      <p>해당되는 공지 판정, 맞춤 피드, 일정과 마감 알림, 신청 현황 관리</p>
      <h2>보관 기간</h2>
      <p>탈퇴할 때까지 보관하며, 내 정보 화면에서 탈퇴하면 바로 삭제합니다.</p>
      <h2>외부 전송</h2>
      <p>학교 게시판의 공지와 첨부 내용은 분석을 위해 외부 AI 서비스로 전송합니다. 위 수집 항목은 외부 AI 서비스로 보내지 않습니다.</p>
      <h2>동의 거부</h2>
      <p>동의하지 않을 수 있으며, 이 경우 서비스 가입이 제한됩니다.</p>
    </section>
  </main>
</template>
