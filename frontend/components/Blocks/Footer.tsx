import Link from 'next/link';

export const Footer = () => {
    return (
        <footer className="border-t border-gray-200 dark:border-gray-800 mt-24">
            <div className="mx-auto max-w-7xl px-6 py-12">
                <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
                    {/* Brand Section */}
                    <div className="col-span-1 md:col-span-1">
                        <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
                            Paperless Meetings
                        </h3>
                        <p className="text-sm text-gray-600 dark:text-gray-400">
                            AI dashboard giúp cán bộ đọc nhanh, hiểu đúng và chuẩn bị câu hỏi cho tài liệu họp.
                        </p>
                    </div>

                    {/* Product Links */}
                    <div>
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
                            Sản phẩm
                        </h4>
                        <ul className="space-y-2">
                            <li>
                                <Link href="#features" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    Dashboard
                                </Link>
                            </li>
                            <li>
                                <Link href="#summary" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    Tóm tắt
                                </Link>
                            </li>
                            <li>
                                <Link href="#qa" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    Hỏi đáp
                                </Link>
                            </li>
                        </ul>
                    </div>

                    {/* Company Links */}
                    <div>
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
                            Triển khai
                        </h4>
                        <ul className="space-y-2">
                            <li>
                                <Link href="#roadmap" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    Roadmap
                                </Link>
                            </li>
                            <li>
                                <Link href="#terms" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    Thuật ngữ
                                </Link>
                            </li>
                            <li>
                                <Link href="#questions" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    Câu hỏi
                                </Link>
                            </li>
                        </ul>
                    </div>

                    {/* Legal Links */}
                    <div>
                        <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">
                            Lưu ý
                        </h4>
                        <ul className="space-y-2">
                            <li>
                                <Link href="#dashboard" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    MVP demo
                                </Link>
                            </li>
                            <li>
                                <Link href="#roadmap" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    Bảo mật
                                </Link>
                            </li>
                            <li>
                                <Link href="#qa" className="text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white transition-colors">
                                    Citation
                                </Link>
                            </li>
                        </ul>
                    </div>
                </div>

                {/* Copyright */}
                <div className="mt-12 pt-8 border-t border-gray-200 dark:border-gray-800">
                    <p className="text-sm text-gray-600 dark:text-gray-400 text-center">
                        © {new Date().getFullYear()} Paperless Meetings MVP.
                    </p>
                </div>
            </div>
        </footer>
    );
};
