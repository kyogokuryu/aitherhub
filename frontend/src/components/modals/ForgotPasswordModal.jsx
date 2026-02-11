import ForgotPassword from "../../pages/authPages/ForgotPassword";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  DialogTrigger,
} from "../ui/dialog";

export default function ForgotPasswordModal({
  trigger,
  open,
  onOpenChange,
  onClose,
}) {
  const handleOpenChange = onOpenChange ?? ((nextOpen) => (!nextOpen ? onClose?.() : null));

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      {trigger ? <DialogTrigger asChild>{trigger}</DialogTrigger> : null}
      <DialogContent className="w-[92vw] max-w-[428px] md:w-[700px] md:h-[500px] md:max-w-none p-0 bg-white">
        <DialogTitle className="sr-only">Reset password</DialogTitle>
        <DialogDescription className="sr-only">Reset password dialog</DialogDescription>
        <div className="p-6 [@media(max-height:650px)]:pt-14 w-full h-full bg-white rounded-[10px]">
          <ForgotPassword onSuccess={() => handleOpenChange(false)} />
        </div>
      </DialogContent>
    </Dialog>
  );
}
