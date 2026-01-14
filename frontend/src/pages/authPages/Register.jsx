import React, { useState } from "react";
import { toast } from "react-toastify";
import AuthService from "../../base/services/userService";
import { PrimaryButton, SecondaryButton } from "../../components/buttons";

export default function Register({ onSuccess }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [checkbox, setCheckbox] = useState(false);

  const handleRegister = async () => {
    if (!email || !password || !confirmPassword) {
      toast.error("Please fill in all required fields");
      return;
    }

    if (password !== confirmPassword) {
      toast.error("Passwords do not match");
      return;
    }

    if (!checkbox) {
      toast.error("Please agree to the terms and conditions");
      return;
    }

    try {
      // Register and get JWT tokens (tokens are automatically stored by AuthService)
      await AuthService.register(email, password);

      // Get user info from JWT token
      const userInfo = await AuthService.getCurrentUser();

      // Store minimal user info in localStorage for quick display
      // Full user info can be retrieved from JWT token via /me endpoint
      const userData = {
        isLoggedIn: true,
        email: userInfo?.email || email,
      };
      localStorage.setItem("user", JSON.stringify(userData));

      toast.success("Registration successful");
      if (onSuccess) onSuccess();
    } catch (err) {
      const detail =
        err?.response?.data?.detail || err?.message || "Registration failed";
      toast.error(detail);
    }
  };

  return (
    <div className="flex flex-col items-center justify-center space-y-6">
      <h2 className=" pt-[20px] pb-[20px] font-cabin font-medium text-[25px] leading-[30px] h-[30px] text-center flex items-center justify-center text-black">
        新規登録
      </h2>

      <div className="w-full space-y-4 md:space-y-0 md:grid md:grid-cols-[180px_1fr] md:gap-x-6 md:gap-y-6 text-left md:w-[500px]">
        <label className="font-cabin font-bold text-[14px] text-black">
          <span className=""> メールアドレス </span>
          <span className="hidden md:block text-[#646464] text-[12px] font-normal">
            {" "}
            ※半角英字8文字以上{" "}
          </span>
        </label>

        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full h-[40px] border #595757 rounded-[5px] px-4 outline-none focus:border-[#4500FF] text-black"
        />

        <label className="font-cabin font-bold text-[14px] text-black">
          パスワード
          <span className="block text-[#646464] text-[12px] font-normal">
            ※半角英字8文字以上
          </span>
        </label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full h-[40px] border #595757 rounded-[5px] px-4 outline-none focus:border-[#4500FF] text-black"
        />

        <label className="font-cabin font-bold text-[14px] text-black">
          パスワードを再入力
          <span className="block text-[#646464] text-[12px] font-normal">
            ※半角英字8文字以上
          </span>
        </label>
        <input
          type="password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          className="w-full h-[40px] border #595757 rounded-[5px] px-4 outline-none focus:border-[#4500FF] text-black"
        />
      </div>

      <div className="flex flex-col items-start w-full space-y-3 md:w-[350px]">
        <div className="text-sm text-center text-gray-600">
          <span className="text-[#4500FF] underline cursor-pointer">
            利用規約
          </span>{" "}
          と
          <span className="text-[#4500FF] underline cursor-pointer">
            プライバシーポリシー
          </span>{" "}
          をご確認ください。
        </div>

        <div className="text-sm text-center text-gray-600">
          <label className="flex items-center justify-center gap-2 text-sm text-black cursor-pointer select-none">
            <input
              type="checkbox"
              checked={checkbox}
              onChange={(e) => setCheckbox(e.target.checked)}
              className="sr-only"
            />

            {/* Custom checkbox */}
            <span
              className={`
                w-[23px] h-[23px]
                rounded-[6px]
                border border-[#8F9393]
                flex items-center justify-center
                transition-all duration-150 ease-out
                ${checkbox ? "bg-[#7D01FF]" : "bg-transparent"}
                active:scale-[0.92]
              `}
            >
              {/* Check icon */}
              <svg
                viewBox="0 0 24 24"
                className={`
                  w-[20px] h-[20px]
                  text-white
                  transition-all duration-150 ease-out
                  ${checkbox ? "opacity-100 scale-100" : "opacity-0 scale-75"}
                `}
                fill="none"
                stroke="#ffffff"
                strokeWidth="3"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </span>

            <span>同意します</span>
          </label>
        </div>
      </div>

      <div className="flex flex-col md:flex-row items-center gap-4 w-full mt-[5px] align-center md:justify-center md:gap-[30px] md:mt-0">
        <PrimaryButton onClick={handleRegister} rounded="rounded-[5px]">
          登録する
        </PrimaryButton>

        <SecondaryButton
          onClick={() => {
            if (onSuccess) onSuccess();
          }}
        >
          キャンセル
        </SecondaryButton>
      </div>
    </div>
  );
}
